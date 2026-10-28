from __future__ import annotations

import atexit
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from filelock import FileLock

from xvenv import versions
from xvenv.platforms import (
    ACTIVE_COMPILER_WRAPPER_DIR_VAR,
    COMPILER_WRAPPER_DIR_VAR,
    build_platform_env,
)
from xvenv.platforms.emscripten import pywasmcross

# `pip_wrapper.py` is only ever executed inside a cross venv; importing it here
# would import pip and register its atexit hook in *this* process. Refer to it
# by path, and keep its filenames in sync with the constants it defines (a
# test checks that they match).
PIP_WRAPPER_SOURCE = Path(__file__).parent / "pip_wrapper.py"
PIP_WRAPPER_NAME = "_pip-wrapper.py"
PIP_PATCHED_NAME = "pip_patched"

# The pip console scripts that a venv installs: `pip`, `pip3`, `pip3.14`.
# Anything else starting with "pip" (pip-compile, pipx, pip-audit, ...) is
# not ours to touch.
PIP_SCRIPT_RE = re.compile(r"pip(3(\.\d+)?)?")

VALID_ARCHES = {"wasm32": "wasm32"}


class AlwaysWasm32:
    """A `DEFAULT_ARCH` mapping: every host architecture targets wasm32."""

    def __getitem__(self, arch):
        return "wasm32"


DEFAULT_ARCH = AlwaysWasm32()

# The Pyodide release whose cross-build environment (xbuildenv) is used for
# each supported Python series. Adding a series here is all that's needed to
# support it (plus expected values in the live test suite).
PYODIDE_VERSIONS = {
    "3.12": "0.27.8",
    "3.13": "0.29.5",
    "3.14": "314.0.7",
}

# Environment variables that build tools use to find compilers, and the
# pywasmcross symlink that each should point at. Mirrors pyodide-build's
# `SYMLINK_ENV_VARS`.
SYMLINK_ENV_VARS = {
    "cc": "CC",
    "c++": "CXX",
    "ld": "LD",
    "lld": "LLD",
    "ar": "AR",
    "gcc": "GCC",
    "ranlib": "RANLIB",
    "strip": "STRIP",
    # For scikit-build to find cmake
    # (https://github.com/scikit-build/scikit-build-core/pull/603)
    "cmake": "CMAKE_EXECUTABLE",
}

# Environment variables that can be used to override the compiler flags that
# are passed to Emscripten when building extension modules. The names match
# the ones used by pyodide-build.
CFLAGS_VAR = "SIDE_MODULE_CFLAGS"
CXXFLAGS_VAR = "SIDE_MODULE_CXXFLAGS"
LDFLAGS_VAR = "SIDE_MODULE_LDFLAGS"

# The meson cross file that the `meson` wrapper passes to `meson setup`. This
# is pyodide-build's `emscripten.meson.cross`; compiler paths are omitted so
# that meson picks the compilers up from CC/CXX/AR (i.e., the wrappers).
MESON_CROSS_FILE_VAR = "MESON_CROSS_FILE"
MESON_CROSS_FILE_NAME = "emscripten.meson.cross"
MESON_CROSS_FILE = """\
[binaries]
exe_wrapper = 'node'
pkg-config = 'pkg-config'

[properties]
needs_exe_wrapper = true
skip_sanity_check = true
longdouble_format = 'IEEE_QUAD_LE'

[host_machine]
system = 'emscripten'
cpu_family = 'wasm32'
cpu = 'wasm'
endian = 'little'
"""

# The environment variables that `emsdk_env.sh` sets. Mirrors pyodide-build's
# `EMSDK_ENV_VARS`.
EMSDK_ENV_VARS = {"PATH", "EMSDK", "EMSDK_NODE", "EMSDK_PYTHON", "SSL_CERT_FILE"}
EMSDK_REPO = "https://github.com/emscripten-core/emsdk"

# Written into an emsdk install directory once install, activation and
# patching have all completed. A directory without this marker is a failed
# (or interrupted) install, and is removed and retried.
EMSDK_COMPLETE_MARKER = ".xbuild-complete"

UNKNOWN_VERSION = "unknown"


###########################################################################
# Locating the target Python build
###########################################################################
def download_url(version_info: tuple, multiarch: str) -> str:
    """Compute the download URL for the Pyodide cross-build environment that
    matches a Python version.

    :param version_info: The `sys.version_info` tuple for the version being
        requested.
    :param multiarch: Ignored; this is always wasm32.
    :returns: The download URL.
    :raises ValueError: if the Python version isn't supported on Emscripten.
    """
    series = versions.series(version_info)
    try:
        pyodide_version = PYODIDE_VERSIONS[series]
    except KeyError:
        raise ValueError(
            f"xbuild doesn't support Python {series} on Emscripten "
            f"(supported: {', '.join(PYODIDE_VERSIONS)})"
        ) from None
    return (
        "https://github.com/pyodide/pyodide/releases/download/"
        f"{pyodide_version}/xbuildenv-{pyodide_version}.tar.gz"
    )


def config_path(extracted_path: Path, version_info, multiarch: str) -> Path:
    """Locate the sysconfigdata file inside an extracted Pyodide xbuildenv.

    :param extracted_path: The root of the extracted archive.
    :param version_info: A `sys.version_info`-shaped value for the Python
        version the archive contains.
    :param multiarch: Ignored; this is always wasm32.
    :returns: The path to the `_sysconfigdata__emscripten_wasm32-emscripten.py`
        module. If the archive doesn't contain a build of the requested Python
        series, the returned path won't exist (the caller reports that).
    """
    installs = extracted_path / "xbuildenv/pyodide-root/cpython/installs"
    series = versions.series(version_info)
    candidates = sorted(installs.glob(f"python-{series}.*"))
    python_dir = candidates[-1] if candidates else installs / f"python-{series}"
    return python_dir / "sysconfigdata/_sysconfigdata__emscripten_wasm32-emscripten.py"


def prefix_path(config_data_path: Path) -> Path:
    """Determine the install prefix of the target Python from the location of
    a build-details.json/sysconfigdata.py file.

    Pyodide's xbuildenv stores a copy of the sysconfigdata at
    `<prefix>/sysconfigdata/`; the install itself (and build-details.json)
    uses the standard `<prefix>/lib/pythonX.Y/` layout.
    """
    if config_data_path.parent.name == "sysconfigdata":
        return config_data_path.parents[1]
    return config_data_path.parents[2]


def archive_path(path: Path) -> Path:
    """Determine the root of the Python archive based on the location of a
    build_details.json/sysconfigdata.py file.

    For Emscripten, the "archive" is the install prefix of the target Python
    (e.g. Pyodide's `cpython/installs/python-X.Y.Z`).
    """
    return prefix_path(path)


def pyodide_root(prefix: Path) -> Path | None:
    """The root of the Pyodide cross-build environment that contains a target
    Python prefix, or `None` if the prefix isn't part of one.

    An xbuildenv lays out `<root>/cpython/installs/python-X.Y.Z` alongside
    `<root>/Makefile.envs`, `<root>/dist`, and `<root>/emsdk/patches`.
    """
    parents = prefix.parents
    if len(parents) > 2 and (parents[2] / "Makefile.envs").is_file():
        return parents[2]
    return None


###########################################################################
# Determining the Emscripten version of the target build
###########################################################################
def _version_from_makefile_envs(root: Path) -> str | None:
    target = "export PYODIDE_EMSCRIPTEN_VERSION ?="
    with (root / "Makefile.envs").open(encoding="utf-8") as f:
        for line in f:
            if line.startswith(target):
                return line.removeprefix(target).strip()
    return None


def _version_from_toolchain(sysconfigdata: dict) -> str | None:
    """Recover the Emscripten version from toolchain paths in sysconfigdata.

    The Emscripten SDK installs its tools in a `.../emsdk-X.Y.Z/upstream/...`
    or `.../emscripten/X.Y.Z/...` directory, which is recorded in the config
    vars naming the toolchain binaries (not necessarily all of them; Pyodide's
    sysconfigdata records `CC` as a bare `cc`, but `AR` as a full path).
    """
    for var in ("CC", "CXX", "AR", "LINKCC", "LDSHARED"):
        for part in Path(sysconfigdata.get(var) or "").parts:
            candidate = part.removeprefix("emsdk-")
            if candidate.count(".") == 2 and candidate.replace(".", "").isdigit():
                return candidate
    return None


def emscripten_version(prefix: Path, sysconfigdata: dict) -> str:
    """Determine the Emscripten version a target Python build was compiled
    with, falling back to `"unknown"`.

    :param prefix: The install prefix of the target Python.
    :param sysconfigdata: The target's sysconfig variables.
    """
    if version := sysconfigdata.get("EMSCRIPTEN_VERSION"):
        return version
    if (root := pyodide_root(prefix)) is not None and (
        version := _version_from_makefile_envs(root)
    ):
        return version
    return _version_from_toolchain(sysconfigdata) or UNKNOWN_VERSION


def patch_sysconfig(prefix: Path, sysconfigvars: dict) -> dict:
    """Record the Emscripten version in the localized sysconfig variables, so
    it is available to anything that only has the sysconfigdata to go on."""
    sysconfigvars["EMSCRIPTEN_VERSION"] = emscripten_version(prefix, sysconfigvars)
    return sysconfigvars


def build_details_from_sysconfigdata(sysconfigdata):
    # Reconstruct a build_details-alike structure from sysconfigdata.
    version = (
        sysconfigdata.get("EMSCRIPTEN_VERSION")
        or _version_from_toolchain(sysconfigdata)
        or UNKNOWN_VERSION
    )
    build_details = {
        "platform": (
            f"{sysconfigdata['MACHDEP']}-{version}-"
            f"{sysconfigdata['MULTIARCH'].split('-')[0]}"
        ),
    }
    return build_details


def extend_context(context, build_details):
    emscripten_version = build_details["platform"].split("-")[1]
    # `packaging.tags.platform_tags()` (and hence pip) dispatches on
    # `platform.system() == "Emscripten"`.
    context["os"] = "Emscripten"
    context["release"] = emscripten_version
    context["platform_version"] = emscripten_version
    context["machine"] = context["arch"]

    context["os_sysname"] = "Emscripten"
    context["os_nodename"] = "emscripten"
    context["os_release"] = emscripten_version
    context["os_version"] = "#1"

    context["sys_extra"] = ""
    # The stdlib's `_pyrepl.trace` (imported by `pdb`, and hence by pytest)
    # does `from posix import _emscripten_log` when sys.platform is
    # emscripten. Provide a stand-in so that such imports don't fail on the
    # build machine.
    context["os_extra"] = """
    import posix

    if not hasattr(posix, "_emscripten_log"):
        def _emscripten_log(message):
            print(message, file=sys.stderr)

        posix._emscripten_log = _emscripten_log
"""
    context["platform_extra"] = f"""
    @monkeypatch(platform)
    def libc_ver() -> int:
        return ("emscripten", "{emscripten_version}")
"""


###########################################################################
# Build environment preparation
###########################################################################
def _sysconfig_vars(config) -> tuple[Path, dict]:
    """Load the (localized) sysconfig variables of the target Python build.

    :param config: The resolved `xvenv.convert.CrossVenvConfig`.
    :returns: A tuple of the target Python's install prefix, and its sysconfig
        variables with build-time paths rewritten to point into that prefix.
    :raises ValueError: if the sysconfigdata can't be found.
    """
    # Imported here to avoid a circular import; `xvenv.convert` imports the
    # platform modules.
    from xvenv.convert import localized_vars
    from xvenv.fetch import parse_sysconfigdata

    if config.sysconfigdata_path:
        sysconfigdata_path = config.sysconfigdata_path
    else:
        with open(config.build_details_path, encoding="utf-8") as fp:
            build_details = json.load(fp)
        abiflags = "".join(build_details["abi"]["flags"])
        sysconfigdata_path = (
            config.build_details_path.parent
            / f"_sysconfigdata_{abiflags}_{config.platform}_{config.multiarch}.py"
        )

    if not sysconfigdata_path.is_file():
        raise ValueError(f"Could not find {sysconfigdata_path}")

    prefix = prefix_path(sysconfigdata_path)
    build_time_vars = parse_sysconfigdata(sysconfigdata_path).build_time_vars
    return prefix, patch_sysconfig(prefix, localized_vars(build_time_vars, prefix))


def _is_ldflag(flag: str) -> bool:
    """Should a CFLAGS entry also be passed when linking?

    Emscripten requires the exception handling / setjmp-longjmp mode (and the
    optimization level) to match between compile and link steps.
    """
    return flag.startswith(("-fwasm-exceptions", "-fexceptions", "-sSUPPORT_LONGJMP"))


def compile_flags(sysconfigdata: dict) -> tuple[str, str, str]:
    """Determine the default flags to use when building extension modules.

    Pyodide builds extension modules as Emscripten "side modules"; the base
    flags are the ones the interpreter itself was configured with, plus the
    library directory of the target Python build.

    :param sysconfigdata: The localized sysconfig variables of the target build.
    :returns: A `(cflags, cxxflags, ldflags)` tuple. Each may be overridden by
        setting `SIDE_MODULE_CFLAGS`, `SIDE_MODULE_CXXFLAGS`, or
        `SIDE_MODULE_LDFLAGS` in the environment.
    """
    configure_cflags = (sysconfigdata.get("CONFIGURE_CFLAGS") or "").split()
    configure_ldflags = (sysconfigdata.get("CONFIGURE_LDFLAGS") or "").split()

    cflags = [*configure_cflags, "-Oz"]
    cxxflags: list[str] = []
    ldflags = [
        *configure_ldflags,
        *(flag for flag in configure_cflags if _is_ldflag(flag)),
        f"-L{sysconfigdata['LIBDIR']}",
        "-Oz",
    ]

    return (
        os.environ.get(CFLAGS_VAR, " ".join(cflags)),
        os.environ.get(CXXFLAGS_VAR, " ".join(cxxflags)),
        os.environ.get(LDFLAGS_VAR, " ".join(ldflags)),
    )


def make_command_wrapper_symlinks(symlink_dir: Path) -> dict[str, str]:
    """Create symlinks that make pywasmcross look like a compiler.

    :param symlink_dir: The directory where the symlinks will be created.
    :returns: The dictionary of compiler environment variables that point to
        the symlinks.
    """
    pywasmcross_exe = symlink_dir / "pywasmcross.py"
    shutil.copy2(pywasmcross.__file__, pywasmcross_exe)
    pywasmcross_exe.chmod(0o755)

    env = {}
    for symlink in pywasmcross.SYMLINKS:
        symlink_path = symlink_dir / symlink
        if symlink_path.is_dir() and not symlink_path.is_symlink():
            shutil.rmtree(symlink_path)
        elif os.path.lexists(symlink_path):
            # remove any stale symlink so it can be re-created
            symlink_path.unlink()

        symlink_path.symlink_to(pywasmcross_exe)
        if symlink in SYMLINK_ENV_VARS:
            env[SYMLINK_ENV_VARS[symlink]] = str(symlink_path)

    return env


def _create_symlink_dir() -> Path:
    """Create the directory that will hold the compiler wrapper symlinks.

    If `XBUILD_COMPILER_WRAPPER_DIR` is set, that directory is used (and left
    in place afterwards, which helps with reproducing problems). Otherwise, a
    temporary directory is created, and removed when the process exits.
    """
    if explicit := os.environ.get(COMPILER_WRAPPER_DIR_VAR):
        symlink_dir = Path(explicit).resolve()
        symlink_dir.mkdir(parents=True, exist_ok=True)
    else:
        symlink_dir = Path(tempfile.mkdtemp(prefix="pywasmcross-"))
        atexit.register(shutil.rmtree, symlink_dir, ignore_errors=True)

    return symlink_dir


###########################################################################
# Emscripten SDK management
###########################################################################
def _run(command: list, **kwargs) -> subprocess.CompletedProcess:
    """Run a build-platform tool, converting failures into `ValueError`s."""
    kwargs.setdefault("env", build_platform_env())
    try:
        return subprocess.run([str(arg) for arg in command], check=True, **kwargs)
    except FileNotFoundError:
        raise ValueError(
            f"Could not find {command[0]!r}, which is needed to install the "
            "Emscripten SDK. Install it, or install and activate the Emscripten "
            "SDK yourself so that `emcc` is on your PATH."
        ) from None
    except subprocess.CalledProcessError as e:
        raise ValueError(
            f"{shlex.join(str(arg) for arg in command)} failed with exit code "
            f"{e.returncode}."
        ) from e


def installed_emscripten_version(emcc: str) -> str | None:
    """The version of an installed `emcc`, or `None` if it can't be determined.

    :param emcc: The path to the `emcc` executable.
    """
    try:
        result = subprocess.run(
            [emcc, "--version"],
            capture_output=True,
            text=True,
            check=True,
            env=build_platform_env(),
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    # The first line looks like "emcc (Emscripten gcc/clang-like replacement
    # + linker emulating GNU ld) 5.0.3 (abc123)".
    for line in result.stdout.splitlines():
        if line.startswith("emcc") and (match := re.search(r"\b(\d+\.\d+\.\d+)", line)):
            return match.group(1)
    return None


def apply_patches(emsdk_path: Path, root: Path) -> None:
    """Apply Pyodide's patches to an Emscripten install.

    Pyodide builds its interpreter with a handful of patches to Emscripten,
    shipped in the xbuildenv's `emsdk/patches` directory; extension modules
    need to be built with the same patches.

    :param emsdk_path: The emsdk install directory.
    :param root: The root of the Pyodide cross-build environment.
    """
    patches_dir = root / "emsdk/patches"
    emscripten_root = emsdk_path / "upstream/emscripten"
    # `GIT_DIR=.` prevents `git apply` from finding the parent emsdk git repo
    # and applying patches relative to it (and silently skipping them).
    patch_env = build_platform_env() | {"GIT_DIR": "."}
    for patch_file in sorted(patches_dir.glob("*.patch")):
        _run(
            ["git", "apply", "--verbose", patch_file],
            cwd=emscripten_root,
            env=patch_env,
        )


def install_emsdk(version: str, cache_path: Path, root: Path | None) -> Path:
    """Install (if needed) an Emscripten SDK of a specific version into the
    cache directory.

    :param version: The Emscripten version to install.
    :param cache_path: The xbuild cache directory.
    :param root: The root of the Pyodide cross-build environment whose
        Emscripten patches should be applied, or `None` to apply no patches.
    :returns: The emsdk install directory.
    :raises ValueError: if the install fails.
    """
    emsdk_path = cache_path / f"emsdk_{version}"
    marker = emsdk_path / EMSDK_COMPLETE_MARKER

    with FileLock(f"{emsdk_path}.lock"):
        if marker.exists():
            return emsdk_path

        if emsdk_path.exists():
            print(f"Removing incomplete Emscripten SDK install at {emsdk_path}...")
            shutil.rmtree(emsdk_path)

        print(f"Installing Emscripten SDK {version} into {emsdk_path}...")
        print("(This downloads the toolchain, and may take a while.)")
        _run(["git", "clone", "--depth=1", EMSDK_REPO, emsdk_path.name], cwd=cache_path)
        emsdk = emsdk_path / "emsdk"
        _run([emsdk, "install", version], cwd=emsdk_path)
        _run([emsdk, "activate", version], cwd=emsdk_path)
        if root is not None:
            print("Applying Pyodide's Emscripten patches...")
            apply_patches(emsdk_path, root)

        marker.touch()
        print(f"Emscripten SDK {version} installed.")

    return emsdk_path


def emsdk_env(emsdk_path: Path) -> dict[str, str]:
    """The environment variables that activating an Emscripten SDK sets.

    :param emsdk_path: The emsdk install directory.
    :returns: The `PATH`, `EMSDK`, etc. values that `emsdk_env.sh` exports.
    :raises ValueError: if the activation script can't be run.
    """
    activate = emsdk_path / "emsdk_env.sh"
    result = _run(
        ["bash", "-c", f"EMSDK_QUIET=1 source {shlex.quote(str(activate))} && env -0"],
        capture_output=True,
        text=True,
    )

    env = {}
    for entry in result.stdout.split("\0"):
        key, sep, value = entry.partition("=")
        if sep and key in EMSDK_ENV_VARS:
            env[key] = value
    if "PATH" not in env:
        raise ValueError(f"Activating the Emscripten SDK at {emsdk_path} failed.")
    return env


def ensure_emscripten(version: str, cache_path: Path, root: Path | None) -> dict:
    """Make sure an Emscripten toolchain matching the target build is
    available, installing one into the cache if needed.

    If `emcc` is already on `PATH` at the right version (or the required
    version is unknown), it is used as-is. Otherwise, a matching SDK is
    installed into the cache directory (if it isn't already there), and the
    environment variables that activate it are returned.

    :param version: The Emscripten version the target was built with, or
        `"unknown"`.
    :param cache_path: The xbuild cache directory.
    :param root: The root of the Pyodide cross-build environment (whose
        Emscripten patches should be applied to a fresh install), or `None`.
    :returns: Environment variables that activate the toolchain (empty if
        the `emcc` already on `PATH` is being used).
    :raises ValueError: if no suitable toolchain can be found or installed.
    """
    emcc = shutil.which("emcc")
    if emcc is not None:
        installed = installed_emscripten_version(emcc)
        if version == UNKNOWN_VERSION or installed in {None, version}:
            return {}
        print(
            f"The emcc on PATH ({emcc}) is Emscripten {installed}, but the target "
            f"Python was built with Emscripten {version}."
        )
    elif version == UNKNOWN_VERSION:
        raise ValueError(
            "Could not find `emcc` on PATH, and the Emscripten version of the "
            "target Python build could not be determined, so a matching Emscripten "
            "SDK can't be installed automatically. Install and activate the "
            "Emscripten SDK that was used to build the target Python."
        )

    emsdk_path = install_emsdk(version, cache_path, root)
    return emsdk_env(emsdk_path)


def prepare_env(config) -> dict[str, str]:
    """Prepare the environment so that compiler invocations are redirected
    through pywasmcross to the Emscripten toolchain.

    An Emscripten SDK matching the target Python build is located (or
    installed into the cache). A "compiler wrapper" directory is created
    containing a copy of `pywasmcross.py` and symlinks to it named `cc`,
    `c++`, `ar`, `cmake`, and so on. That directory is prepended to PATH, and
    `CC`/`CXX`/`AR`/etc. are pointed at the symlinks. The arguments
    pywasmcross needs (compiler flags, include and library paths, the Pyodide
    ABI version) are passed both via the `PYWASMCROSS_ARGS` environment
    variable, and a JSON file alongside the symlinks (in case some tool
    filters the environment).

    :param config: The resolved `xvenv.convert.CrossVenvConfig`.
    :returns: A dict of environment variables to merge into `os.environ`.
    :raises ValueError: if the target build's sysconfigdata can't be loaded
        or doesn't describe a Pyodide ABI, or an Emscripten toolchain can't be
        found or installed.
    """
    prefix, sysconfigdata = _sysconfig_vars(config)
    root = pyodide_root(prefix)
    version = sysconfigdata["EMSCRIPTEN_VERSION"]

    # The ABI version determines the wheel tag, and some compiler behaviour
    # (see `pywasmcross.handle_command_generate_args`); refuse to guess.
    abi = sysconfigdata.get("PYODIDE_ABI_VERSION") or sysconfigdata.get(
        "PYEMSCRIPTEN_PLATFORM_VERSION"
    )
    if not abi:
        raise ValueError(
            f"The Python build at {prefix} doesn't record a Pyodide ABI version "
            "(PYODIDE_ABI_VERSION). xbuild can only build Emscripten wheels "
            "against Pyodide's cross-build environments."
        )

    env: dict[str, str] = {}
    if root is not None:
        env["PYODIDE_ROOT"] = str(root)
    env.update(ensure_emscripten(version, config.cache_path, root))
    # The PATH on which the Emscripten tools can be found, before the
    # wrappers are added.
    base_path = env.get("PATH", os.environ.get("PATH", ""))
    # emsdk doesn't bundle a Python on Linux, so the Emscripten tools would
    # otherwise run under whatever `python3` is first on PATH -- which, during
    # a build, is a cross-platform venv whose `sys.platform` is emscripten.
    if "EMSDK_PYTHON" not in env and "EMSDK_PYTHON" not in os.environ:
        env["EMSDK_PYTHON"] = getattr(sys, "_base_executable", sys.executable)

    cflags, cxxflags, ldflags = compile_flags(sysconfigdata)

    symlink_dir = _create_symlink_dir()
    env.update(make_command_wrapper_symlinks(symlink_dir))

    (symlink_dir / MESON_CROSS_FILE_NAME).write_text(MESON_CROSS_FILE, encoding="utf-8")
    env[MESON_CROSS_FILE_VAR] = os.environ.get(
        MESON_CROSS_FILE_VAR, str(symlink_dir / MESON_CROSS_FILE_NAME)
    )

    args = {
        "cflags": cflags,
        "cxxflags": cxxflags,
        "ldflags": ldflags,
        "target_install_dir": str(prefix),
        "pythoninclude": sysconfigdata["INCLUDEPY"],
        "exports": "pyinit",
        "abi": abi,
        # The PATH to fall back to inside the wrapper if the wrapper directory
        # can't be removed from the inherited PATH.
        "PATH": base_path,
    }

    pywasmcross_env = json.dumps(args)
    # Store into environment variable and to disk. In most cases we will
    # load from the environment variable but if some other tool filters
    # environment variables we will load from disk instead.
    env[pywasmcross.ARGS_ENV_VAR] = pywasmcross_env
    (symlink_dir / pywasmcross.ARGS_FILENAME).write_text(pywasmcross_env)

    env[ACTIVE_COMPILER_WRAPPER_DIR_VAR] = str(symlink_dir)
    env["PATH"] = os.pathsep.join(
        part for part in [str(symlink_dir), base_path] if part
    )
    return env


###########################################################################
# Cross venv customization
###########################################################################
def install_pip_wrapper(venv_path: Path) -> None:
    """Replace the `pip*` scripts of a cross venv with the Emscripten-aware
    pip wrapper.

    pip's stock console script is left to run under the (patched) venv
    interpreter, but it doesn't know about Pyodide's wheel platform tags, and
    its vendored urllib3 would misbehave when `sys.platform` reports
    Emscripten. `pip_wrapper.py` fixes both; this installs it as `pip`.

    :param venv_path: The root of the cross venv.
    """
    venv_bin = venv_path / "bin"
    python = venv_bin / "python3"
    if not python.exists():
        # No bin/python3 means this isn't a Unix-layout venv (or it's broken);
        # there's nothing sensible to install into.
        return

    pips = [path for path in venv_bin.iterdir() if PIP_SCRIPT_RE.fullmatch(path.name)]
    if not pips:
        # The venv was created --without-pip; nothing to wrap.
        return

    wrapper_path = venv_bin / PIP_WRAPPER_NAME
    patched_path = venv_bin / PIP_PATCHED_NAME

    shutil.copy(PIP_WRAPPER_SOURCE, wrapper_path)

    # Other than the monkey patches, this is exactly what normal pip looks
    # like: run the pip entry point under the venv's interpreter.
    patched_path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            exec {shlex.quote(str(python))} -s {shlex.quote(str(wrapper_path))} "$@"
            """
        ),
        encoding="utf-8",
    )
    patched_path.chmod(0o755)

    for pip in pips:
        pip.unlink(missing_ok=True)
        pip.symlink_to(patched_path)


def install_xpython_symlink(venv_path: Path, config) -> None:
    """Expose the Pyodide (node-hosted) interpreter as `bin/xpython` in a
    cross venv created from an xbuildenv, so that code can be run against the
    venv's site-packages on the target.

    :param venv_path: The root of the cross venv.
    :param config: The resolved `xvenv.convert.CrossVenvConfig`.
    """
    root = pyodide_root(config.archive_path)
    if root is None or not (python := root / "dist/python").is_file():
        return

    xpython = venv_path / "bin/xpython"
    xpython.unlink(missing_ok=True)
    xpython.symlink_to(python)


def post_convert(venv_path: Path, config) -> None:
    """Platform-specific steps to run after a venv has been converted into an
    Emscripten cross venv.

    :param venv_path: The root of the cross venv.
    :param config: The resolved `xvenv.convert.CrossVenvConfig`.
    """
    install_pip_wrapper(venv_path)
    install_xpython_symlink(venv_path, config)


###########################################################################
# Testbed
###########################################################################
def packages_path(work_path: Path) -> Path:
    # The Pyodide interpreter (run as `venv/bin/xpython`) picks up the venv's
    # own site-packages, so that's where dependencies need to be installed.
    series = versions.series(sys.version_info)
    return work_path / f"venv/lib/python{series}/site-packages"


def setup_testbed(
    archive_path: Path,
    work_path: Path,
    src_paths: list[Path],
):
    """Stage source files for running on the Emscripten testbed.

    There's no testbed project to clone for Emscripten; the Pyodide
    interpreter is run directly (via the `xpython` symlink installed into the
    cross venv), with the staged sources as its working directory.

    :param archive_path: The target Python install prefix.
    :param work_path: The working directory to stage the sources into.
    :param src_paths: Paths to copy into the `src` directory.
    :raises RuntimeError: if the archive isn't part of a Pyodide xbuildenv
        (which is where the interpreter comes from), or `node` isn't available.
    """
    root = pyodide_root(archive_path)
    if root is None or not (root / "dist/python").is_file():
        raise RuntimeError(
            f"{archive_path} isn't part of a Pyodide cross-build environment; "
            "the Emscripten testbed requires one."
        )
    if shutil.which("node") is None:
        raise RuntimeError("Running the Emscripten testbed requires `node` on PATH.")

    src_path = work_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)

    for src in src_paths:
        if src.is_dir():
            shutil.copytree(src, src_path / src.name, dirs_exist_ok=True)
        else:
            shutil.copy(src, src_path / src.name)


def run_testbed(
    work_path: Path,
    args: list[str],
    verbose: int,
    **kwargs,
) -> int:
    """Run the testbed in the Emscripten (node-hosted) interpreter.

    :param work_path: The working directory containing the cross venv
        (`work_path / "venv"`) and staged sources (`work_path / "src"`).
    :param args: Arguments to pass to the interpreter. Accepts any argument
        list starting with `-c`/`-m`; defaults to `-m test` if `args` is
        empty.
    :param verbose: Verbosity level (unused).
    :returns: The exit code of the subprocess.
    """
    command = [
        str(work_path / "venv/bin/xpython"),
        *(args or ["-m", "test"]),
    ]

    result = subprocess.run(
        command, check=False, cwd=work_path / "src", env=build_platform_env()
    )
    return result.returncode
