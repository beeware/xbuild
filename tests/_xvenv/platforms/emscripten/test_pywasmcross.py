import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from xvenv.platforms.emscripten import XBUILD_ENV_SCRIPTS_DIR_VAR, pywasmcross
from xvenv.platforms.emscripten.pywasmcross import (
    EXPORTED_FUNCTIONS_FLAG,
    CrossCompileArgs,
    ExitCodeWithReason,
    _calculate_object_exports_readobj_parse,
    filter_objects,
    get_cmake_compiler_flags,
    handle_command,
    handle_command_generate_args,
    is_link_cmd,
    load_args,
    path_without_wrappers,
    replay_genargs_handle_dashI,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Emscripten builds require a Unix host"
)


@pytest.fixture(scope="function")
def build_args():
    yield CrossCompileArgs(
        cflags="",
        cxxflags="",
        ldflags="",
        target_install_dir="",
        pythoninclude="python/include",
        exports="whole_archive",
    )


def generate_args(
    line: str, args: CrossCompileArgs, link: bool = False
) -> str | ExitCodeWithReason:
    splitline = line.split()
    res = handle_command_generate_args(splitline, args)
    if isinstance(res, ExitCodeWithReason):
        return res

    if res[0] in ("emcc", "em++"):
        for arg in [
            "-Werror=implicit-function-declaration",
            "-Werror=mismatched-parameter-types",
            "-Werror=return-type",
        ]:
            assert arg in res
            res.remove(arg)

    if "-c" in splitline and "python/include" in res:
        include_index = res.index("python/include")
        del res[include_index]
        del res[include_index - 1]

    if link:
        arg = "-Wl,--fatal-warnings"
        assert arg in res
        res.remove(arg)
    return " ".join(res)


def test_handle_command(build_args):
    args = build_args
    assert handle_command_generate_args(["gcc", "-print-multiarch"], args) == [
        "echo",
        "wasm32-emscripten",
    ]
    assert handle_command_generate_args(["gcc", "-v"], args) == ["emcc", "-v"]

    proxied_commands = {
        "cc": "emcc",
        "c++": "em++",
        "g++": "em++",
        "gcc": "emcc",
        "ld": "emcc",
        "lld": "emcc",
        "ar": "emar",
        "ranlib": "emranlib",
        "strip": "emstrip",
        "cmake": "emcmake",
    }

    for cmd, proxied_cmd in proxied_commands.items():
        assert generate_args(cmd, args).split()[0] == proxied_cmd

    assert (
        generate_args("gcc -c test.o -o test.so", args, True)
        == "emcc -c test.o -o test.so"
    )

    # check cxxflags injection and cpp detection
    args = CrossCompileArgs(
        cflags="-I./lib2",
        cxxflags="-std=c++11",
        ldflags="-lm",
        exports="whole_archive",
    )
    assert (
        generate_args("gcc -I./lib1 -c test.cpp -o test.o", args)
        == "em++ -I./lib1 -c test.cpp -o test.o -I./lib2 -std=c++11"
    )

    # check ldflags injection
    args = CrossCompileArgs(
        cflags="",
        cxxflags="",
        ldflags="-lm",
        target_install_dir="",
        exports="whole_archive",
    )
    assert (
        generate_args("gcc -c test.o -o test.so", args, True)
        == "emcc -c test.o -o test.so -lm"
    )

    # Test that repeated libraries are removed
    assert (
        generate_args("gcc test.o -lbob -ljim -ljim -lbob -o test.so", args, True)
        == "emcc test.o -lbob -ljim -o test.so -lm"
    )


def test_handle_command_passthrough(build_args):
    """Commands that pywasmcross doesn't rewrite are passed through, and the
    caller's argument list is not modified."""
    line = ["cmake", "--build", "."]
    result = handle_command_generate_args(line, build_args)

    assert result == ["cmake", "--build", "."]
    assert result is not line

    line = ["ar", "rc", "lib.a", "a.o"]
    assert handle_command_generate_args(line, build_args) == [
        "emar",
        "rc",
        "lib.a",
        "a.o",
    ]
    assert line == ["ar", "rc", "lib.a", "a.o"]


def test_handle_command_ldflags(build_args):
    # Make sure to remove unsupported link flags for wasm-ld

    args = build_args
    assert (
        generate_args(
            "gcc -Wl,--strip-all,--as-needed "
            "-Wl,--sort-common,-z,now,-Bsymbolic-functions -c test.o -o test.so",
            args,
            True,
        )
        == "emcc -Wl,-z,now -c test.o -o test.so"
    )


def test_handle_command_dashl(build_args):
    """Unavailable libraries are dropped; setjmp/longjmp variants are used for
    newer ABIs."""
    assert (
        generate_args("gcc test.o -lffi -lgfortran -o test.so", build_args, True)
        == "emcc test.o -o test.so"
    )

    old_abi = build_args._replace(abi="2024_0")
    assert (
        generate_args("gcc test.o -lpng -lfreetype -o test.so", old_abi, True)
        == "emcc test.o -lpng -lfreetype -o test.so"
    )

    new_abi = build_args._replace(abi="2025_0")
    assert (
        generate_args("gcc test.o -lpng -lfreetype -o test.so", new_abi, True)
        == "emcc test.o -lpng-legacysjlj -lfreetype-legacysjlj -o test.so"
    )


def test_handle_command_strip_abi(build_args):
    """strip is skipped on ABIs that use Emscripten > 5.0.0 (i.e., 2026_0
    and later)."""
    assert handle_command_generate_args(
        ["strip", "test.so"], build_args._replace(abi="2025_0")
    ) == ["emstrip", "test.so"]
    assert handle_command_generate_args(
        ["strip", "test.so"], build_args._replace(abi="2026_0")
    ) == ["echo", "test.so"]


def test_handle_command_macos_tools(build_args):
    """install_name_tool/otool are no-ops."""
    assert handle_command_generate_args(
        ["install_name_tool", "-id", "x", "y.so"], build_args
    ) == ["echo", "install_name_tool", "-id", "x", "y.so"]


def test_handle_command_meson(build_args, monkeypatch):
    """`meson setup` picks up a cross file from the environment."""
    monkeypatch.delenv("MESON_CROSS_FILE", raising=False)
    assert handle_command_generate_args(["meson", "setup", "build"], build_args) == [
        "meson",
        "setup",
        "build",
    ]
    assert handle_command_generate_args(["meson", "compile"], build_args) == [
        "meson",
        "compile",
    ]

    monkeypatch.setenv("MESON_CROSS_FILE", "/cross.ini")
    assert handle_command_generate_args(["meson", "setup", "build"], build_args) == [
        "meson",
        "setup",
        "--cross-file",
        "/cross.ini",
        "build",
    ]


def test_replay_genargs_handle_dashI():
    """System include directories are dropped; everything else is kept."""
    assert replay_genargs_handle_dashI("-I/usr/include", "/target") is None
    assert replay_genargs_handle_dashI("-I/usr/local/include", "/target") is None
    assert (
        replay_genargs_handle_dashI("-I/target/include/python3.14", "/target")
        == "-I/target/include/python3.14"
    )
    assert replay_genargs_handle_dashI("-I./include", "/target") == "-I./include"


def test_conda_unsupported_args(build_args):
    # Check that compile arguments that are not supported by emcc and are sometimes
    # used in conda are removed.
    args = build_args
    assert generate_args(
        "gcc -c test.o -B /compiler_compat -o test.so", args, True
    ) == ("emcc -c test.o -o test.so")

    assert generate_args("gcc -c test.o -Wl,--sysroot=/ -o test.so", args, True) == (
        "emcc -c test.o -o test.so"
    )


@pytest.mark.parametrize(
    "line, expected",
    [
        ([], []),
        (
            [
                "obj1.o",
                "obj2.o",
                "slib1.so",
                "slib2.so",
                "lib1.a",
                "lib2.a",
                "-o",
                "test.so",
            ],
            ["obj1.o", "obj2.o", "lib1.a", "lib2.a"],
        ),
        (
            ["@dir/link.txt", "obj1.o", "obj2.o", "test.so"],
            ["@dir/link.txt", "obj1.o", "obj2.o"],
        ),
    ],
)
def test_filter_objects(line, expected):
    assert filter_objects(line) == expected


def test_calculate_object_exports_readobj_parse():
    output = """
    Symbol {
        Name: g2
        Type: FUNCTION (0x0)
        Flags [ (0x0)
        ]
        ElementIndex: 0x2
    }
    Symbol {
        Name: f2
        Type: FUNCTION (0x0)
        Flags [ (0x4)
        VISIBILITY_HIDDEN (0x4)
        ]
        ElementIndex: 0x1
    }
    Symbol {
        Name: l
        Type: FUNCTION (0x0)
        Flags [ (0x10)
        UNDEFINED (0x10)
        ]
        ImportModule: env
        ElementIndex: 0x0
    }
    """
    assert _calculate_object_exports_readobj_parse(output) == ["g2"]


def test_calculate_object_exports_readobj_parse_missing_name():
    with pytest.raises(RuntimeError, match="Didn't find symbol's name"):
        _calculate_object_exports_readobj_parse("Symbol {\nFlags [ (0x0)\n]\n}\n")


def test_get_cmake_compiler_flags():
    cmake_flags = " ".join(get_cmake_compiler_flags())

    compiler_flags = (
        "CMAKE_C_COMPILER",
        "CMAKE_CXX_COMPILER",
        "CMAKE_C_COMPILER_AR",
        "CMAKE_CXX_COMPILER_AR",
    )

    for compiler_flag in compiler_flags:
        assert f"-D{compiler_flag}" in cmake_flags

    emscripten_compilers = (
        "emcc",
        "em++",
        "emar",
    )

    for emscripten_compiler in emscripten_compilers:
        assert emscripten_compiler not in cmake_flags


def test_handle_command_cmake(build_args):
    args = build_args

    build_cmd = ["cmake", "--build", ".", "--target", "target"]
    assert handle_command_generate_args(build_cmd, args) == build_cmd


def test_is_link_cmd():
    assert is_link_cmd(["test.so"])
    assert is_link_cmd(["test.so.1.2.3"])
    assert not is_link_cmd(["test", "test.a", "test.o", "test.c", "test.cpp", "test.h"])
    assert not is_link_cmd(["test.so.conf", "-o", "", "-shared"])


@pytest.mark.parametrize("flag", ["-fopenmp", "-fopenmp=libomp", "-fopenmp=libgomp"])
def test_openmp_flags_are_dropped(build_args, flag):
    """Pyodide doesn't support threads and openmp requires them.

    We error out if they are requested.
    """
    res = generate_args(f"cc -c {flag} test.c", build_args)
    assert res == ExitCodeWithReason(1, "openmp requires threads and is not supported")


def test_fopenmp_simd_is_kept(build_args):
    """-fopenmp-simd does not define _OPENMP and does not imply threads."""
    res = generate_args("cc -c -fopenmp-simd test.c", build_args)
    assert "-fopenmp-simd" in res


def test_exports_pyinit(build_args, monkeypatch):
    """With exports="pyinit", the link step becomes a side module exporting
    only the PyInit symbols (via a response file)."""
    monkeypatch.setattr(
        "xvenv.platforms.emscripten.pywasmcross.calculate_object_exports_nm",
        lambda objects: ["PyInit_foo", "helper", "PyInit_bar"],
    )

    res = handle_command_generate_args(
        ["cc", "foo.o", "-o", "foo.so"], build_args._replace(exports="pyinit")
    )

    assert "-sSIDE_MODULE=2" in res
    (exported,) = [arg for arg in res if arg.startswith(EXPORTED_FUNCTIONS_FLAG)]
    response_file = exported.removeprefix(EXPORTED_FUNCTIONS_FLAG)
    with open(response_file) as f:
        assert json.load(f) == ["_PyInit_foo", "_PyInit_bar"]

    # The response file is tracked for removal once the linker has run.
    pywasmcross.cleanup_response_files()
    assert not os.path.exists(response_file)


def test_exports_explicit(build_args):
    """An explicit export list is used as-is."""
    res = handle_command_generate_args(
        ["cc", "foo.o", "-o", "foo.so"], build_args._replace(exports=["a", "b"])
    )

    (exported,) = [arg for arg in res if arg.startswith(EXPORTED_FUNCTIONS_FLAG)]
    with open(exported.removeprefix(EXPORTED_FUNCTIONS_FLAG)) as f:
        assert json.load(f) == ["_a", "_b"]
    pywasmcross.cleanup_response_files()


def test_handle_command_runs_rewritten_command(build_args, monkeypatch):
    """handle_command() runs the rewritten command and returns its exit code."""
    calls = []

    class Result:
        returncode = 3

    def fake_run(args, *a, **kw):
        calls.append(args)
        assert "capture_output" not in kw and "stdout" not in kw
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    assert handle_command(["ar", "rc", "lib.a", "a.o"], build_args) == 3
    assert calls == [["emar", "rc", "lib.a", "a.o"]]


def test_handle_command_rejected(build_args, monkeypatch):
    """handle_command() doesn't run anything if the arguments are rejected."""
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **kw: pytest.fail("should not run")
    )

    result = handle_command(["cc", "-c", "-fopenmp", "x.c"], build_args)

    assert isinstance(result, ExitCodeWithReason)
    assert result.exitcode == 1


def test_load_args_from_env(tmp_path, monkeypatch):
    """Arguments are read from the environment when available."""
    monkeypatch.setenv("PYWASMCROSS_ARGS", json.dumps({"cflags": "-Oz"}))
    (tmp_path / "pywasmcross_env.json").write_text(json.dumps({"cflags": "-O0"}))

    assert load_args(tmp_path / "cc") == {"cflags": "-Oz"}


def test_load_args_from_file(tmp_path, monkeypatch):
    """Arguments fall back to the JSON file beside the invoked symlink."""
    monkeypatch.delenv("PYWASMCROSS_ARGS", raising=False)
    (tmp_path / "pywasmcross_env.json").write_text(json.dumps({"cflags": "-O0"}))

    assert load_args(tmp_path / "cc") == {"cflags": "-O0"}


def test_load_args_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("PYWASMCROSS_ARGS", raising=False)

    with pytest.raises(RuntimeError, match="can't find PYWASMCROSS_ARGS"):
        load_args(tmp_path / "cc")


def test_handle_command_cleans_up_response_file(build_args, monkeypatch):
    """The export response file is removed after the linker has run."""
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **kw: subprocess.CompletedProcess(a[0], 0)
    )
    seen = {}

    def fake_run(args, *a, **kw):
        (exported,) = [arg for arg in args if arg.startswith(EXPORTED_FUNCTIONS_FLAG)]
        seen["path"] = exported.removeprefix(EXPORTED_FUNCTIONS_FLAG)
        assert os.path.exists(seen["path"])
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr("subprocess.run", fake_run)

    assert (
        handle_command(["cc", "x.o", "-o", "x.so"], build_args._replace(exports=["a"]))
        == 0
    )
    assert not os.path.exists(seen["path"])


def test_handle_command_missing_tool(build_args, monkeypatch):
    """A missing Emscripten tool is reported clearly (exit 127, like a shell)."""

    def fake_run(args, *a, **kw):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr("subprocess.run", fake_run)

    result = handle_command(["ar", "rc", "lib.a"], build_args)

    assert isinstance(result, ExitCodeWithReason)
    assert result.exitcode == 127
    assert "cannot find 'emar'" in result.reason


def test_handle_command_signal(build_args, monkeypatch):
    """A tool killed by a signal exits the way a shell would report it."""
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **kw: subprocess.CompletedProcess(a[0], -11)
    )

    assert handle_command(["ar", "rc", "lib.a"], build_args) == 139


def test_path_without_wrappers(tmp_path):
    """The wrapper directory is removed from PATH (however it's spelled);
    everything else stays, with the build env's scripts dir in front."""
    wrappers = tmp_path / "wrappers"
    wrappers.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(wrappers)
    path = os.pathsep.join(
        [str(wrappers), "/isolated/bin", str(alias), "/xbuild/path", "", "/usr/bin"]
    )

    assert path_without_wrappers(path, wrappers, "/fallback", None) == os.pathsep.join(
        ["/isolated/bin", "/xbuild/path", "/usr/bin"]
    )
    assert path_without_wrappers(
        path, wrappers, "/fallback", "/scripts"
    ) == os.pathsep.join(["/scripts", "/isolated/bin", "/xbuild/path", "/usr/bin"])
    # An already-present scripts dir isn't duplicated.
    assert path_without_wrappers(
        path, wrappers, "/fallback", "/isolated/bin"
    ) == os.pathsep.join(["/isolated/bin", "/xbuild/path", "/usr/bin"])


def test_path_without_wrappers_fallback(tmp_path):
    """If nothing is left of PATH, the recorded PATH is used."""
    assert path_without_wrappers(
        str(tmp_path), tmp_path, "/emsdk:/usr/bin", "/scripts"
    ) == os.pathsep.join(["/scripts", "/emsdk", "/usr/bin"])


def test_Xbuild_env_scripts_dir_var_in_sync():
    """pywasmcross can't import xvenv, so it duplicates the variable name."""
    assert pywasmcross.XBUILD_ENV_SCRIPTS_DIR_VAR == XBUILD_ENV_SCRIPTS_DIR_VAR


###########################################################################
# End-to-end: invoke the wrapper through a symlink, as a build backend would.
###########################################################################
@pytest.fixture
def wrapper_dir(tmp_path):
    """A compiler wrapper directory (as `prepare_env()` creates it), a fake
    `emcc` that records its arguments and exits 3, and a PATH on which the
    wrappers shadow it."""
    wrappers = tmp_path / "wrappers"
    wrappers.mkdir()
    exe = wrappers / "pywasmcross.py"
    exe.write_bytes(Path(pywasmcross.__file__).read_bytes())
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    for name in pywasmcross.SYMLINKS:
        (wrappers / name).symlink_to(exe)

    toolchain = tmp_path / "emsdk"
    toolchain.mkdir()
    record = tmp_path / "emcc-args.json"
    recorder = tmp_path / "record.py"
    recorder.write_text(
        "import json, os, sys\n"
        f"with open({str(record)!r}, 'w') as f:\n"
        "    json.dump(dict(argv=sys.argv[1:], path=os.environ['PATH']), f)\n"
    )
    for tool in ("emcc", "em++", "emar"):
        fake = toolchain / tool
        fake.write_text(f'#!/bin/sh\n{sys.executable} {recorder} "$@"\nexit 3\n')
        fake.chmod(0o755)
    # The interpreter running the test must be reachable as `python3`.
    python_dir = tmp_path / "python"
    python_dir.mkdir()
    (python_dir / "python3").symlink_to(sys.executable)

    return SimpleNamespace(
        dir=wrappers,
        record=record,
        path=os.pathsep.join([str(wrappers), str(toolchain), str(python_dir)]),
        toolchain=toolchain,
        python_dir=python_dir,
    )


def _invoke(wrapper_dir, tool, *args, env=None, cwd=None):
    environ = {
        "PATH": wrapper_dir.path,
        pywasmcross.ARGS_ENV_VAR: json.dumps(
            {
                "cflags": "-Oz",
                "cxxflags": "",
                "ldflags": "-L/target/lib",
                "target_install_dir": "/target",
                "pythoninclude": "/target/include/python3.14",
                "exports": "whole_archive",
                "abi": "2026_0",
                "PATH": str(wrapper_dir.toolchain),
            }
        ),
        **(env or {}),
    }
    return subprocess.run(
        [str(wrapper_dir.dir / tool), *args],
        env=environ,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_end_to_end_compile(wrapper_dir):
    """`cc -c` becomes `emcc -c` with the cross flags appended, runs with the
    wrappers removed from PATH, and propagates the exit code."""
    result = _invoke(wrapper_dir, "cc", "-c", "x.c", "-o", "x.o")

    assert result.returncode == 3, result.stderr
    recorded = json.loads(wrapper_dir.record.read_text())
    assert recorded["argv"] == [
        "-c",
        "x.c",
        "-o",
        "x.o",
        "-Werror=implicit-function-declaration",
        "-Werror=mismatched-parameter-types",
        "-Werror=return-type",
        "-Oz",
        "-I",
        "/target/include/python3.14",
    ]
    assert recorded["path"].split(os.pathsep) == [
        str(wrapper_dir.toolchain),
        str(wrapper_dir.python_dir),
    ]


def test_end_to_end_scripts_dir(wrapper_dir):
    """The build environment's scripts directory is put in front of PATH."""
    _invoke(
        wrapper_dir,
        "c++",
        "-c",
        "x.cpp",
        env={XBUILD_ENV_SCRIPTS_DIR_VAR: "/isolated/bin"},
    )

    recorded = json.loads(wrapper_dir.record.read_text())
    assert recorded["path"].split(os.pathsep)[0] == "/isolated/bin"


def test_end_to_end_args_from_file(wrapper_dir):
    """Without the environment variable, the arguments are read from the JSON
    file beside the symlinks."""
    (wrapper_dir.dir / pywasmcross.ARGS_FILENAME).write_text(
        json.dumps(
            {
                "cflags": "-Os",
                "cxxflags": "",
                "ldflags": "",
                "target_install_dir": "",
                "pythoninclude": "",
                "exports": "whole_archive",
                "abi": "",
                "PATH": str(wrapper_dir.toolchain),
            }
        )
    )
    result = subprocess.run(
        [str(wrapper_dir.dir / "cc"), "-c", "x.c"],
        env={"PATH": wrapper_dir.path},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 3, result.stderr
    assert json.loads(wrapper_dir.record.read_text())["argv"][-1] == "-Os"


def test_end_to_end_rejected(wrapper_dir):
    """Rejected flags produce a message on stderr and a non-zero exit, without
    running the compiler."""
    result = _invoke(wrapper_dir, "cc", "-c", "-fopenmp", "x.c")

    assert result.returncode == 1
    assert "openmp requires threads" in result.stderr
    assert not wrapper_dir.record.exists()


def test_end_to_end_missing_emcc(wrapper_dir):
    """A missing toolchain is reported clearly."""
    for tool in wrapper_dir.toolchain.iterdir():
        tool.unlink()

    result = _invoke(wrapper_dir, "cc", "-c", "x.c")

    assert result.returncode == 127
    assert "cannot find 'emcc' on PATH" in result.stderr
