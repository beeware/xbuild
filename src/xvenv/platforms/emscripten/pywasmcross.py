#!/usr/bin/env python3
"""Helper for cross-compiling Python binary extensions for Emscripten.

Python has never had a proper cross-compilation story. This is a hack, which
miraculously works, to get around that. The gist is we compile the package
replacing calls to the compiler and linker with wrappers that adjust include
paths and flags as necessary for cross-compiling and then pass the command
along to Emscripten.

This file is copied into a "compiler wrapper" directory (see
`xvenv.platforms.emscripten.prepare_env()`), and a symlink is created for each
name in `SYMLINKS` pointing at the copy. When invoked through one of those
symlinks, the module acts as that tool. When imported normally (e.g., from the
test suite, or by `prepare_env()`), it only exposes the helper functions.

This file must only depend on the standard library: it runs under whichever
`python3` is first on PATH when a build backend invokes a compiler, which is
not necessarily the interpreter that xbuild itself is running under.

Ported from pyodide-build's `pywasmcross.py`
(https://github.com/pyodide/pyodide-build/blob/45caaca689e8366ea34811f920d246ee5323644c/pyodide_build/pywasmcross.py).
The Fortran (`gfortran`/f2c) and scipy-specific handling has been removed, as
those are concerns of the Pyodide recipe system rather than general
cross-compilation; Rust/cargo support has not been ported.

Copyright (c) 2019-2026, Pyodide contributors. Modifications copyright (c)
2026, the xbuild contributors.

This Source Code Form is subject to the terms of the Mozilla Public License,
v. 2.0. If a copy of the MPL was not distributed with this file, You can obtain
one at https://mozilla.org/MPL/2.0/. See LICENSE.third-party in the xbuild
source distribution.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NamedTuple, NoReturn

try:
    from __main__ import __file__ as INVOKED_PATH_STR
except ImportError:  # pragma: no cover - e.g. `python -c` or an interactive shell
    INVOKED_PATH_STR = ""

INVOKED_PATH = Path(INVOKED_PATH_STR)

# The name of the JSON file (stored alongside the wrapper symlinks) that holds
# the cross-compile arguments, and the environment variable that may hold the
# same content.
ARGS_ENV_VAR = "PYWASMCROSS_ARGS"
ARGS_FILENAME = "pywasmcross_env.json"

# The environment variable that names the directory where tools installed into
# an isolated build environment (cmake, meson, ninja, ...) can be found. This
# duplicates `xvenv.platforms.BUILD_ENV_SCRIPTS_DIR_VAR` (this module can't
# import xvenv); a test keeps the two in sync.
BUILD_ENV_SCRIPTS_DIR_VAR = "XBUILD_BUILD_ENV_SCRIPTS_DIR"

SYMLINKS = {
    "cc",
    "c++",
    "ld",
    "lld",
    "ar",
    "gcc",
    "g++",
    "ranlib",
    "strip",
    "cmake",
    "meson",
    "install_name_tool",
    "otool",
}
IS_COMPILER_INVOCATION = INVOKED_PATH.name in SYMLINKS


def load_args(invoked_path: Path) -> dict:
    """Load the cross-compile arguments for a compiler invocation.

    The arguments are read from the `PYWASMCROSS_ARGS` environment variable
    if possible; otherwise, from the `pywasmcross_env.json` file in the same
    directory as the invoked symlink.

    :param invoked_path: The path of the symlink that was invoked.
    :returns: The decoded argument dictionary.
    :raises RuntimeError: if the arguments can't be found.
    """
    if ARGS_ENV_VAR in os.environ:
        return json.loads(os.environ[ARGS_ENV_VAR])

    try:
        with open(invoked_path.parent / ARGS_FILENAME) as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(
            f"Invalid invocation: can't find {ARGS_ENV_VAR}."
            f" Invoked from {invoked_path}."
        ) from None


def path_without_wrappers(
    path: str, wrapper_dir: Path, fallback: str, scripts_dir: str | None
) -> str:
    """Compute the PATH that wrapped tools should run with.

    Removing the wrapper directory from PATH is essential: when (for example)
    the `cmake` wrapper execs `emcmake cmake`, we need `cmake` to resolve to
    the real binary, not back to this wrapper. Everything else that was on
    PATH (the isolated build environment, `XBUILD_PATH`, the Emscripten SDK)
    stays visible.

    :param path: The PATH the wrapper was invoked with.
    :param wrapper_dir: The directory containing the wrapper symlinks.
    :param fallback: The PATH to use if nothing is left after removing the
        wrapper directory (e.g., a build tool scrubbed PATH); this is the PATH
        recorded when the wrappers were created.
    :param scripts_dir: The directory where tools installed into an isolated
        build environment live, or `None`. Kept at the front.
    :returns: The new PATH.
    """
    wrapper_dir = wrapper_dir.resolve()
    parts = []
    for part in path.split(os.pathsep):
        if not part:
            continue
        try:
            if Path(part).resolve() == wrapper_dir:
                continue
        except OSError:  # pragma: no cover - unresolvable PATH entries
            pass
        parts.append(part)
    if not parts:
        parts = [part for part in fallback.split(os.pathsep) if part]
    if scripts_dir and scripts_dir not in parts:
        parts.insert(0, scripts_dir)
    return os.pathsep.join(parts)


if IS_COMPILER_INVOCATION:
    PYWASMCROSS_ARGS = load_args(INVOKED_PATH)

    os.environ["PATH"] = path_without_wrappers(
        os.environ.get("PATH", ""),
        INVOKED_PATH.parent,
        PYWASMCROSS_ARGS.pop("PATH", ""),
        os.environ.get(BUILD_ENV_SCRIPTS_DIR_VAR),
    )


class CrossCompileArgs(NamedTuple):
    """
    Arguments for cross-compiling a package.
    """

    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""

    target_install_dir: str = ""  # The path to the target Python installation
    pythoninclude: str = ""  # path to the cross-compiled Python include directory
    exports: Literal["whole_archive", "requested", "pyinit"] | list[str] = "pyinit"
    # Pyodide ABI, e.g., 2025_0
    # Sometimes we have to inject compile flags only for certain ABIs.
    abi: str = ""


@dataclass
class ExitCodeWithReason:
    exitcode: int
    reason: str


def _missing_tool(name: str) -> NoReturn:
    print(
        f"pywasmcross: cannot find {name!r} on PATH; is the Emscripten SDK "
        "installed and activated?",
        file=sys.stderr,
    )
    sys.exit(127)


def is_link_cmd(line: list[str]) -> bool:
    """
    Check if the command is a linker invocation.
    """
    for arg in line:
        if not arg or arg[0] == "-":
            continue

        if arg.endswith(".so"):
            return True

        dot_so_pos = arg.find(".so.")
        if dot_so_pos != -1:
            version = arg[dot_so_pos + 4 :]
            # versioned shared libraries start with a digit, and consist of
            # only digits and dots.
            if (
                version
                and version[0].isdigit()
                and all(c.isdigit() or c == "." for c in version)
            ):
                return True

    return False


def replay_genargs_handle_dashl(arg: str, used_libs: set[str], abi: str) -> str | None:
    """
    Figure out how to replace a `-lsomelib` argument.

    :param arg: The argument we are replacing. Must start with `-l`.
    :param used_libs: The libraries we've used so far in this command. emcc
        fails out if `-lsomelib` occurs twice, so we have to track this.
    :param abi: The Pyodide ABI version string (e.g. `2026_0`).
    :returns: The new argument, or None to delete the argument.
    """
    assert arg.startswith("-l")

    if arg in {"-lffi", "-lgfortran"}:
        return None

    # Some Emscripten libraries that use setjmp/longjmp.
    # The Emscripten linker should automatically know to use these variants so
    # this shouldn't be necessary.
    if abi > "2025" and arg in ("-lfreetype", "-lpng"):
        arg += "-legacysjlj"

    # WASM link doesn't like libraries being included twice
    # skip second one
    if arg in used_libs:
        return None
    used_libs.add(arg)
    return arg


def replay_genargs_handle_dashI(arg: str, target_install_dir: str) -> str | None:
    """
    Figure out how to replace a `-Iincludepath` argument.

    :param arg: The argument we are replacing. Must start with `-I`.
    :param target_install_dir: The target Python installation directory.
    :returns: The new argument, or None to delete the argument.
    """
    assert arg.startswith("-I")

    include_path_str = arg[2:]

    # Don't include any system directories
    if include_path_str.startswith("/usr"):
        return None
    return arg


def replay_genargs_handle_linker_opts(arg: str) -> str | None:
    """
    Ignore some link flags.

    It should not check if `arg == "-Wl,-xxx"` and ignore directly here,
    because arg may be something like "-Wl,-xxx,-yyy" where we only want
    to ignore "-xxx" but not "-yyy".
    """
    assert arg.startswith("-Wl")

    excluded_linker_opts = (
        "-Bsymbolic-functions",
        # breaks emscripten see https://github.com/emscripten-core/emscripten/issues/14460
        "--strip-all",
        "-strip-all",
        # wasm-ld does not recognize some link flags
        "--sort-common",
        "--as-needed",
        # macOS-specific linker flags that wasm-ld doesn't understand
        "-headerpad_max_install_names",
        "-dead_strip_dylibs",
        # Newer clang seems to add this by default, but wasm-ld doesn't support it
        "--enable-new-dtags",
    )

    excluded_linker_prefixes = (
        "--sysroot=",  # ignore unsupported --sysroot compile argument used in conda
        "--version-script=",
        "-R/",  # wasm-ld does not accept -R (runtime libraries)
        "-R.",  # wasm-ld does not accept -R (runtime libraries)
        "--exclude-libs=",
    )

    link_opts = arg.split(",")[1:]
    new_link_opts = ["-Wl"]

    for opt in link_opts:
        if opt in excluded_linker_opts:
            continue

        if opt.startswith(excluded_linker_prefixes):
            continue

        new_link_opts.append(opt)

    if len(new_link_opts) > 1:
        return ",".join(new_link_opts)
    else:
        return None


def replay_genargs_handle_argument(arg: str) -> str | ExitCodeWithReason | None:
    """
    Figure out how to replace a general argument.

    :param arg: The argument we are replacing. Must not start with `-I`,
        `-l` or `-Wl,`.
    :returns: The new argument, or None to delete the argument.
    """
    assert not arg.startswith("-I")  # should be handled by other functions
    assert not arg.startswith("-l")
    assert not arg.startswith("-Wl,")

    # Don't include any system directories
    if arg.startswith("-L/usr"):
        return None

    # fmt: off
    excluded_arguments = (
        # threading is disabled for now
        "-pthread",
        # this only applies to compiling fortran code, but we already f2c'd
        "-ffixed-form",
        "-fallow-argument-mismatch",
        # On Mac, we need to omit some darwin-specific arguments
        "-bundle", "-undefined", "dynamic_lookup",
        # This flag is needed to build numpy with SIMD optimization which we
        # currently disable
        "-mpopcnt",
        # gcc flag that clang does not support
        "-Bsymbolic-functions",
        '-fno-second-underscore',
        '-fstack-protector',  # doesn't work?
        '-fno-strict-overflow',  # warning: argument unused during compilation
        "-mno-sse2", # warning: argument unused during compilation
        "-mno-avx2", # warning: argument unused during compilation
        "-std=legacy", # fortran flag that clang does not support
    )
    # fmt: on

    if arg in excluded_arguments:
        return None

    if arg.startswith("-J"):  # fortran flag that clang does not support
        return None

    # Emscripten 6.0.3 added OpenMP support but Pyodide doesn't support threads.
    # Exit with nonzero status code so that we treat OpenMP as unavailable.
    # Leave -fopenmp-simd alone since simd is okay.
    if arg.startswith("-fopenmp=") or arg == "-fopenmp":
        return ExitCodeWithReason(1, "openmp requires threads and is not supported")

    return arg


def get_cmake_compiler_flags() -> list[str]:
    """
    Generate cmake compiler flags.

    emcmake will set these values to emcc, em++, ... but we need to set them to
    cc, c++, in order to make them pass through pywasmcross.

    :returns: The commandline flags to pass to cmake.
    """
    compiler_flags = {
        "CMAKE_C_COMPILER": "cc",
        "CMAKE_CXX_COMPILER": "c++",
        "CMAKE_AR": "ar",
        "CMAKE_C_COMPILER_AR": "ar",
        "CMAKE_CXX_COMPILER_AR": "ar",
    }

    flags = []
    symlinks_dir = INVOKED_PATH.parent
    for key, value in compiler_flags.items():
        assert value in SYMLINKS

        flags.append(f"-D{key}={symlinks_dir / value}")

    return flags


def _calculate_object_exports_readobj_parse(output: str) -> list[str]:
    """
    >>> _calculate_object_exports_readobj_parse(
    ...     '''
    ...     Format: WASM \\n Arch: wasm32 \\n AddressSize: 32bit
    ...     Sections [
    ...         Section { \\n Type: TYPE (0x1)   \\n Size: 5  \\n Offset: 8  \\n }
    ...         Section { \\n Type: IMPORT (0x2) \\n Size: 32 \\n Offset: 19 \\n }
    ...     ]
    ...     Symbol {
    ...         Name: g2 \\n Type: FUNCTION (0x0) \\n
    ...         Flags [ (0x0) \\n ]
    ...         ElementIndex: 0x2
    ...     }
    ...     Symbol {
    ...         Name: f2 \\n Type: FUNCTION (0x0) \\n
    ...         Flags [ (0x4) \\n VISIBILITY_HIDDEN (0x4) \\n ]
    ...         ElementIndex: 0x1
    ...     }
    ...     Symbol {
    ...         Name: l  \\n Type: FUNCTION (0x0)
    ...         Flags [ (0x10)\\n UNDEFINED (0x10) \\n ]
    ...         ImportModule: env
    ...         ElementIndex: 0x0
    ...     }
    ...     '''
    ... )
    ['g2']
    """
    result = []
    insymbol = False
    for line in output.split("\n"):
        line = line.strip()
        if line == "Symbol {":
            insymbol = True
            export = True
            name = None
            symbol_lines = [line]
            continue
        if not insymbol:
            continue
        symbol_lines.append(line)
        if line.startswith("Name:"):
            name = line.removeprefix("Name:").strip()
        if line.startswith(("BINDING_LOCAL", "UNDEFINED", "VISIBILITY_HIDDEN")):
            export = False
        if line == "}":
            insymbol = False
            if export:
                if not name:
                    raise RuntimeError(
                        "Didn't find symbol's name:\n" + "\n".join(symbol_lines)
                    )
                result.append(name)
    return result


def calculate_object_exports_readobj(objects: list[str]) -> list[str] | None:
    from shutil import which
    from subprocess import run as sp_run

    # This works for bootstrapped Emscripten via GitHub sources.
    # llvm-readobj might not be available this way with Homebrew
    # or conda-forge distributions of Emscripten.
    which_emcc = which("emcc")
    if not which_emcc:
        _missing_tool("emcc")
    emcc = Path(which_emcc)
    readobj = (emcc / "../../bin/llvm-readobj").resolve()
    readobj_path: str | None
    if readobj.exists():
        readobj_path = str(readobj)
    else:
        readobj_path = which("llvm-readobj")
    if not readobj_path:
        _missing_tool("llvm-readobj")

    args = [
        readobj_path,
        "--section-details",
        "-st",
    ] + objects
    completedprocess = sp_run(
        args,
        encoding="utf8",
        capture_output=True,
        check=False,
    )
    if completedprocess.returncode:
        print(
            f"Command '{' '.join(args)}' failed. Output to stderr was:",
            file=sys.stderr,
        )
        print(completedprocess.stderr, file=sys.stderr)
        sys.exit(completedprocess.returncode)

    if "bitcode files are not supported" in completedprocess.stderr:
        return None

    return _calculate_object_exports_readobj_parse(completedprocess.stdout)


def calculate_object_exports_nm(objects: list[str]) -> list[str]:
    from subprocess import run as sp_run

    args = ["emnm", "-j", "--export-symbols"] + objects
    try:
        result = sp_run(
            args,
            encoding="utf8",
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        _missing_tool("emnm")
    if result.returncode:
        print(
            f"Command '{' '.join(args)}' failed. Output to stderr was:",
            file=sys.stderr,
        )
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.splitlines()


def filter_objects(line: list[str]) -> list[str]:
    """
    Collect up all the object files and archive files being linked.
    """
    return [
        arg
        for arg in line
        if arg.endswith((".a", ".o"))
        # response file (https://gcc.gnu.org/wiki/Response_Files)
        or arg.startswith("@")
    ]


def calculate_exports(line: list[str], export_all: bool) -> Iterable[str]:
    """
    List out symbols from object files and archive files that are marked as
    public. If ``export_all`` is ``True``, then return all public symbols. If
    not, return only the public symbols that begin with `PyInit`.
    """
    objects = filter_objects(line)
    exports = None
    # Using emnm is simpler but it cannot handle bitcode. If we're only
    # exporting the PyInit symbols, save effort by using nm.
    if export_all:
        exports = calculate_object_exports_readobj(objects)
    if exports is None:
        # Either export_all is false or we are linking at least one bitcode
        # object. Fall back to a more conservative estimate of the symbols
        # exported. This can export things with `__visibility__("hidden")`
        exports = calculate_object_exports_nm(objects)
    if export_all:
        return exports
    return (x for x in exports if x.startswith("PyInit"))


EXPORTED_FUNCTIONS_FLAG = "-sEXPORTED_FUNCTIONS=@"
# Response files created by `get_export_flags()` that haven't been cleaned up.
_RESPONSE_FILES: list[str] = []


def cleanup_response_files() -> None:
    """Remove the export response files created for the current command."""
    while _RESPONSE_FILES:
        try:
            os.unlink(_RESPONSE_FILES.pop())
        except OSError:  # pragma: no cover
            pass


def get_export_flags(
    line: list[str],
    exports: Literal["whole_archive", "requested", "pyinit"] | list[str],
) -> Iterator[str]:
    """
    If "whole_archive" was requested, no action is needed. Otherwise, add
    `-sSIDE_MODULE=2` and the appropriate export list.
    """
    from tempfile import NamedTemporaryFile

    if exports == "whole_archive":
        return
    yield "-sSIDE_MODULE=2"
    if isinstance(exports, str):
        export_list = calculate_exports(line, exports == "requested")
    else:
        export_list = exports

    prefixed_exports = ["_" + x for x in export_list]

    with NamedTemporaryFile(mode="w", delete=False) as f:
        # Use a response file to avoid command line length limits
        f.write(json.dumps(prefixed_exports))

    # The file has to outlive this function (the linker reads it), so it is
    # removed by `handle_command()` once the linker has run.
    _RESPONSE_FILES.append(f.name)
    yield f"{EXPORTED_FUNCTIONS_FLAG}{f.name}"


def handle_command_generate_args(
    line: list[str], build_args: CrossCompileArgs
) -> list[str] | ExitCodeWithReason:
    """
    A helper command for `handle_command` that generates the new arguments for
    the compilation.

    This doesn't run the compiler itself. The one exception to being
    side-effect free is the link step of a side module: computing the export
    list runs `emnm`/`llvm-readobj` over the objects being linked, and writes
    the result to a response file (see `get_export_flags()`).

    :param line: The original compilation command as a list e.g.,
        ``["gcc", "-c", "input.c", "-o", "output.c"]``. Not modified.
    :param build_args: The arguments that pywasmcross was invoked with
    :returns: An updated argument list suitable for use with emscripten.

    >>> args = CrossCompileArgs(exports="whole_archive")
    >>> handle_command_generate_args(['gcc', 'test.c'], args)
    ['emcc', 'test.c', '-Werror=implicit-function-declaration', ...]
    """
    line = list(line)
    if "-print-multiarch" in line:
        return ["echo", "wasm32-emscripten"]
    if len(line) == 2 and line[1] == "-v":
        return ["emcc", "-v"]

    cmd = line[0]
    if cmd in {"c++", "g++"}:
        new_args = ["em++"]
    elif cmd in {"cc", "gcc", "ld", "lld"}:
        new_args = ["emcc"]
        # distutils doesn't use the c++ compiler when compiling c++ <sigh>
        if any(arg.endswith((".cpp", ".cc")) for arg in line):
            new_args = ["em++"]
    elif cmd == "ar":
        line[0] = "emar"
        return line
    elif cmd == "cmake":
        # If it is a build/install command, or running a script, we don't do
        # anything.
        if "--build" in line or "--install" in line or "-P" in line or "-E" in line:
            return line

        flags = get_cmake_compiler_flags()
        line[:1] = [
            "emcmake",
            "cmake",
            *flags,
        ]
        return line
    elif cmd == "meson":
        if line[:2] != ["meson", "setup"]:
            return line

        if "MESON_CROSS_FILE" in os.environ:
            line[:2] = [
                "meson",
                "setup",
                "--cross-file",
                os.environ["MESON_CROSS_FILE"],
            ]

        return line
    elif cmd in {"install_name_tool", "otool"}:
        # In MacOS, meson tries to run install_name_tool to fix the rpath of
        # the shared library assuming that it is an ELF file. We need to skip
        # this step. See: https://github.com/mesonbuild/meson/issues/8027
        return ["echo", *line]
    elif cmd == "ranlib":
        line[0] = "emranlib"
        return line
    elif cmd == "strip":
        if build_args.abi > "2026":
            # Emscripten > 5.0.0 strips out the dylink.0 section
            # so we skip strip to avoid the error
            # https://github.com/emscripten-core/emscripten/issues/26563
            line[0] = "echo"
        else:
            line[0] = "emstrip"
        return line
    else:
        return line

    used_libs: set[str] = set()
    # Go through and adjust arguments
    for arg in line[1:]:
        if new_args[-1].startswith("-B") and "compiler_compat" in arg:
            # conda uses custom compiler search paths with the compiler_compat
            # folder. Ignore it.
            del new_args[-1]
            continue

        result: str | ExitCodeWithReason | None
        if arg.startswith("-l"):
            result = replay_genargs_handle_dashl(arg, used_libs, build_args.abi)
        elif arg.startswith("-I"):
            result = replay_genargs_handle_dashI(arg, build_args.target_install_dir)
        elif arg.startswith("-Wl"):
            result = replay_genargs_handle_linker_opts(arg)
        else:
            result = replay_genargs_handle_argument(arg)

        if isinstance(result, ExitCodeWithReason):
            return result

        if result:
            new_args.append(result)

    new_args.extend(
        [
            "-Werror=implicit-function-declaration",
            "-Werror=mismatched-parameter-types",
            "-Werror=return-type",
        ]
    )

    # set linker and C flags to error on anything to do with function
    # declarations being wrong. Better to fail at compile or link time.
    if is_link_cmd(line):
        new_args.append("-Wl,--fatal-warnings")
        new_args.extend(build_args.ldflags.split())
        new_args.extend(get_export_flags(line, build_args.exports))

    if "-c" in line:
        if new_args[0] == "emcc":
            new_args.extend(build_args.cflags.split())
        elif new_args[0] == "em++":
            new_args.extend(build_args.cflags.split() + build_args.cxxflags.split())

        if build_args.pythoninclude:
            new_args.extend(["-I", build_args.pythoninclude])

    return new_args


def handle_command(
    line: list[str],
    build_args: CrossCompileArgs,
) -> int | ExitCodeWithReason:
    """Handle a compilation command.

    :param line: The compilation arguments.
    :param build_args: A container with additional compilation options.
    :returns: The exit code of the (rewritten) command, or an
        `ExitCodeWithReason` if the command was rejected outright.
    """
    from subprocess import run as sp_run

    new_args = handle_command_generate_args(line, build_args)
    if isinstance(new_args, ExitCodeWithReason):
        return new_args

    try:
        result = sp_run(new_args, check=False)
    except FileNotFoundError:
        return ExitCodeWithReason(
            127,
            f"pywasmcross: cannot find {new_args[0]!r} on PATH; is the Emscripten "
            "SDK installed and activated?",
        )
    finally:
        cleanup_response_files()

    if result.returncode < 0:
        # Killed by a signal; report it the way a shell would.
        return 128 - result.returncode
    return result.returncode


def compiler_main() -> None:
    try:
        build_args = CrossCompileArgs(
            cflags=PYWASMCROSS_ARGS["cflags"],
            cxxflags=PYWASMCROSS_ARGS["cxxflags"],
            ldflags=PYWASMCROSS_ARGS["ldflags"],
            target_install_dir=PYWASMCROSS_ARGS["target_install_dir"],
            pythoninclude=PYWASMCROSS_ARGS["pythoninclude"],
            exports=PYWASMCROSS_ARGS["exports"],
            abi=PYWASMCROSS_ARGS["abi"],
        )
    except KeyError as e:
        print(
            f"pywasmcross: {ARGS_ENV_VAR} is missing the {e.args[0]!r} key; was it "
            "written by an older version of xbuild?",
            file=sys.stderr,
        )
        sys.exit(1)

    args = list(sys.argv)
    args[0] = Path(args[0]).name
    result = handle_command(args, build_args)
    if isinstance(result, ExitCodeWithReason):
        print(result.reason, file=sys.stderr)
        exitcode = result.exitcode
    else:
        exitcode = result
    sys.exit(exitcode)


if IS_COMPILER_INVOCATION:
    compiler_main()
