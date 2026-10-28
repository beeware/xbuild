import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from xvenv.convert import CrossVenvConfig
from xvenv.platforms import ACTIVE_COMPILER_WRAPPER_DIR_VAR, COMPILER_WRAPPER_DIR_VAR
from xvenv.platforms import emscripten as emscripten_module
from xvenv.platforms.emscripten import (
    EMSDK_COMPLETE_MARKER,
    MESON_CROSS_FILE,
    MESON_CROSS_FILE_VAR,
    PIP_PATCHED_NAME,
    PIP_WRAPPER_NAME,
    SYMLINK_ENV_VARS,
    archive_path,
    build_details_from_sysconfigdata,
    compile_flags,
    config_path,
    download_url,
    emscripten_version,
    emsdk_env,
    ensure_emscripten,
    extend_context,
    install_emsdk,
    install_pip_wrapper,
    install_xpython_symlink,
    installed_emscripten_version,
    make_command_wrapper_symlinks,
    packages_path,
    patch_sysconfig,
    post_convert,
    prefix_path,
    prepare_env,
    pyodide_root,
    pywasmcross,
    run_testbed,
    setup_testbed,
)

from ...utils import VersionInfo

PREFIX = "/build/python-3.14.2"
EMSDK = "/opt/emsdk/emsdk-5.0.3/upstream/emscripten"

BUILD_TIME_VARS = {
    "prefix": PREFIX,
    "LDLIBRARY": "libpython3.14.a",
    "VERSION": "3.14",
    "ABIFLAGS": "",
    "MACHDEP": "emscripten",
    "MULTIARCH": "wasm32-emscripten",
    "CC": "cc",
    "CXX": "c++",
    "AR": f"{EMSDK}/emar",
    "LIBDIR": f"{PREFIX}/lib",
    "INCLUDEPY": f"{PREFIX}/include/python3.14",
    "CONFIGURE_CFLAGS": (
        "-O2 -g0 -fPIC -fwasm-exceptions -sSUPPORT_LONGJMP=wasm -DPY_CALL_TRAMPOLINE"
    ),
    "CONFIGURE_LDFLAGS": "",
    "PYODIDE_ABI_VERSION": "2026_0",
}

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Emscripten builds require a Unix host"
)


def _xbuildenv(tmp_path, emscripten="5.0.3", python="3.14.2"):
    """A fake Pyodide xbuildenv, returning the target Python prefix."""
    root = tmp_path / "xbuildenv/pyodide-root"
    (root / "Makefile.envs").parent.mkdir(parents=True, exist_ok=True)
    (root / "Makefile.envs").write_text(
        f"export PYODIDE_EMSCRIPTEN_VERSION ?= {emscripten}\n"
        "export PYODIDE_ABI_VERSION ?= 2026_0\n"
    )
    (root / "dist").mkdir(exist_ok=True)
    (root / "dist/python").write_text("#!/bin/sh\n")
    (root / "emsdk/patches").mkdir(parents=True, exist_ok=True)
    prefix = root / "cpython/installs" / f"python-{python}"
    prefix.mkdir(parents=True, exist_ok=True)
    return prefix


def _emscripten_sysconfigdata(
    prefix, build_time_vars=BUILD_TIME_VARS, layout="lib/python3.14"
):
    """An Emscripten sysconfigdata file inside a prefix layout (either the
    install's own `lib/pythonX.Y`, or the xbuildenv's `sysconfigdata`)."""
    path = prefix / layout / "_sysconfigdata__emscripten_wasm32-emscripten.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"build_time_vars = {build_time_vars!r}\n")
    return path


def _emscripten_build_details(prefix):
    """A build-details.json (plus the sysconfigdata it implies) inside a
    prefix layout."""
    sysconfigdata_path = _emscripten_sysconfigdata(prefix)
    path = sysconfigdata_path.parent / "build-details.json"
    path.write_text(
        json.dumps(
            {
                "platform": "emscripten-5.0.3-wasm32",
                "implementation": {"_multiarch": "wasm32-emscripten"},
                "language": {"version": "3.14"},
                "abi": {"flags": []},
            }
        )
    )
    return path


def _emscripten_config(
    prefix,
    sysconfigdata_path=None,
    build_details_path=None,
    cache_path=None,
):
    return Mock(
        spec=CrossVenvConfig,
        platform="emscripten",
        multiarch="wasm32-emscripten",
        archive_path=prefix,
        build_details_path=build_details_path,
        sysconfigdata_path=sysconfigdata_path,
        cache_path=cache_path,
    )


@pytest.fixture
def which(monkeypatch):
    """Control what `shutil.which()` finds inside the platform module."""
    found = {}
    monkeypatch.setattr(
        emscripten_module.shutil, "which", lambda cmd, *a, **kw: found.get(cmd)
    )
    return found


@pytest.fixture
def fake_emcc(which, monkeypatch):
    """An `emcc` on PATH at the version used by `_xbuildenv()`."""
    which["emcc"] = "/opt/emsdk/emcc"
    monkeypatch.setattr(
        emscripten_module, "installed_emscripten_version", lambda emcc: "5.0.3"
    )


@pytest.fixture
def no_flag_overrides(monkeypatch):
    for var in ("SIDE_MODULE_CFLAGS", "SIDE_MODULE_CXXFLAGS", "SIDE_MODULE_LDFLAGS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv(MESON_CROSS_FILE_VAR, raising=False)
    monkeypatch.delenv("EMSDK_PYTHON", raising=False)


###########################################################################
# Locating the target Python build
###########################################################################
@pytest.mark.parametrize(
    ("version_details", "url"),
    [
        pytest.param(
            {"major": 3, "minor": 14, "micro": 7, "releaselevel": "final", "serial": 0},
            "https://github.com/pyodide/pyodide/releases/download/314.0.7/xbuildenv-314.0.7.tar.gz",
            id="3.14",
        ),
        pytest.param(
            {"major": 3, "minor": 13, "micro": 2, "releaselevel": "final", "serial": 0},
            "https://github.com/pyodide/pyodide/releases/download/0.29.5/xbuildenv-0.29.5.tar.gz",
            id="3.13",
        ),
        pytest.param(
            {"major": 3, "minor": 12, "micro": 9, "releaselevel": "final", "serial": 0},
            "https://github.com/pyodide/pyodide/releases/download/0.27.8/xbuildenv-0.27.8.tar.gz",
            id="3.12",
        ),
    ],
)
def test_download_url(version_details, url):
    """The Pyodide xbuildenv download URL is determined by the Python version."""
    version_info = VersionInfo(**version_details)

    assert download_url(version_info, "wasm32") == url


@pytest.mark.parametrize("minor", [11, 15])
def test_download_url_unsupported(minor):
    """Python versions without a Pyodide release are rejected clearly."""
    with pytest.raises(ValueError, match=f"doesn't support Python 3.{minor}"):
        download_url(VersionInfo(3, minor, 0, "final", 0), "wasm32")


def test_config_path(tmp_path):
    """The sysconfigdata inside an extracted Pyodide xbuildenv can be located,
    regardless of the micro version it contains."""
    installs = tmp_path / "xbuildenv/pyodide-root/cpython/installs"
    for name in ("python-3.13.9", "python-3.14.2"):
        sysconfigdata = installs / name / "sysconfigdata/_sysconfigdata.py"
        sysconfigdata.parent.mkdir(parents=True)
        sysconfigdata.touch()
    version_info = VersionInfo(3, 14, 7, "final", 0)

    assert config_path(tmp_path, version_info, "wasm32") == (
        installs
        / "python-3.14.2/sysconfigdata/_sysconfigdata__emscripten_wasm32-emscripten.py"
    )


def test_config_path_missing(tmp_path):
    """If the archive doesn't contain the requested series, a (non-existent)
    path is still returned so the caller can report it."""
    path = config_path(tmp_path, VersionInfo(3, 14, 7, "final", 0), "wasm32")

    assert not path.exists()
    assert "python-3.14" in str(path)


@pytest.mark.parametrize(
    "relative_path",
    [
        pytest.param("lib/python3.14/build-details.json", id="build-details"),
        pytest.param("lib/python3.14/_sysconfigdata_x.py", id="install-sysconfigdata"),
        pytest.param("sysconfigdata/_sysconfigdata_x.py", id="xbuildenv-sysconfigdata"),
    ],
)
def test_prefix_path(relative_path):
    """The install prefix (which is also the "archive") can be found from any
    of the layouts in which the configuration files are shipped."""
    path = Path("/some/prefix") / relative_path

    assert prefix_path(path) == Path("/some/prefix")
    assert archive_path(path) == Path("/some/prefix")


def test_pyodide_root(tmp_path):
    """The xbuildenv root is found from a prefix inside it, and not from a
    standalone prefix."""
    prefix = _xbuildenv(tmp_path)

    assert pyodide_root(prefix) == tmp_path / "xbuildenv/pyodide-root"
    assert pyodide_root(tmp_path / "standalone/python") is None
    assert pyodide_root(Path("/")) is None


###########################################################################
# Determining the Emscripten version
###########################################################################
def test_emscripten_version_from_xbuildenv(tmp_path):
    """Inside an xbuildenv, the version comes from Makefile.envs."""
    prefix = _xbuildenv(tmp_path, emscripten="4.0.9")

    assert emscripten_version(prefix, {**BUILD_TIME_VARS, "AR": "ar"}) == "4.0.9"


@pytest.mark.parametrize(
    ("overrides", "version"),
    [
        pytest.param({}, "5.0.3", id="from-AR"),
        pytest.param(
            {"CC": f"{EMSDK.replace('5.0.3', '4.0.12')}/emcc"},
            "4.0.12",
            id="from-CC",
        ),
        pytest.param(
            {"AR": "/opt/emscripten/6.0.4/bin/emar"},
            "6.0.4",
            id="bare-version-dir",
        ),
        pytest.param({"CC": "cc", "CXX": "c++", "AR": "ar"}, "unknown", id="none"),
    ],
)
def test_emscripten_version_from_toolchain(tmp_path, overrides, version):
    """Outside an xbuildenv, the version is recovered from toolchain paths in
    the sysconfigdata, falling back to "unknown"."""
    prefix = tmp_path / "standalone"

    assert emscripten_version(prefix, {**BUILD_TIME_VARS, **overrides}) == version


def test_emscripten_version_already_patched(tmp_path):
    """A version recorded by `patch_sysconfig()` wins."""
    prefix = _xbuildenv(tmp_path, emscripten="4.0.9")

    assert (
        emscripten_version(prefix, {**BUILD_TIME_VARS, "EMSCRIPTEN_VERSION": "1.2.3"})
        == "1.2.3"
    )


def test_patch_sysconfig(tmp_path):
    """patch_sysconfig records the Emscripten version in the sysconfig vars."""
    prefix = _xbuildenv(tmp_path)

    patched = patch_sysconfig(prefix, dict(BUILD_TIME_VARS))

    assert patched["EMSCRIPTEN_VERSION"] == "5.0.3"
    assert patched["prefix"] == PREFIX


@pytest.mark.parametrize(
    ("overrides", "version"),
    [
        pytest.param({"EMSCRIPTEN_VERSION": "4.0.9"}, "4.0.9", id="patched"),
        pytest.param({}, "5.0.3", id="toolchain"),
        pytest.param({"AR": "ar"}, "unknown", id="none"),
    ],
)
def test_build_details_from_sysconfigdata(overrides, version):
    """Build details prefer the patched version, then the toolchain paths."""
    build_details = build_details_from_sysconfigdata({**BUILD_TIME_VARS, **overrides})

    assert build_details == {"platform": f"emscripten-{version}-wasm32"}


def test_extend_context():
    """The cross-target context is populated from the build details."""
    context = {"arch": "wasm32", "sdk": "emscripten"}

    extend_context(context, {"platform": "emscripten-5.0.3-wasm32"})

    assert context["os"] == "Emscripten"
    assert context["release"] == "5.0.3"
    assert context["platform_version"] == "5.0.3"
    assert context["machine"] == "wasm32"
    assert context["os_sysname"] == "Emscripten"
    assert context["os_release"] == "5.0.3"
    assert "_emscripten_log" in context["os_extra"]
    assert '("emscripten", "5.0.3")' in context["platform_extra"]


###########################################################################
# Compiler flags and wrappers
###########################################################################
def test_compile_flags(no_flag_overrides):
    """Side-module flags are derived from the configure-time flags of the
    target build."""
    cflags, cxxflags, ldflags = compile_flags(BUILD_TIME_VARS)

    assert cflags == (
        "-O2 -g0 -fPIC -fwasm-exceptions -sSUPPORT_LONGJMP=wasm "
        "-DPY_CALL_TRAMPOLINE -Oz"
    )
    assert cxxflags == ""
    assert ldflags == f"-fwasm-exceptions -sSUPPORT_LONGJMP=wasm -L{PREFIX}/lib -Oz"


def test_compile_flags_configure_ldflags(no_flag_overrides):
    """Configure-time LDFLAGS are preserved."""
    _, _, ldflags = compile_flags(
        {**BUILD_TIME_VARS, "CONFIGURE_LDFLAGS": "-sWASM_BIGINT"}
    )

    assert ldflags == (
        f"-sWASM_BIGINT -fwasm-exceptions -sSUPPORT_LONGJMP=wasm -L{PREFIX}/lib -Oz"
    )


def test_compile_flags_overrides(monkeypatch):
    """The flags can be overridden from the environment."""
    monkeypatch.setenv("SIDE_MODULE_CFLAGS", "-Os")
    monkeypatch.setenv("SIDE_MODULE_CXXFLAGS", "-std=c++17")
    monkeypatch.setenv("SIDE_MODULE_LDFLAGS", "-sWASM_BIGINT")

    assert compile_flags(BUILD_TIME_VARS) == ("-Os", "-std=c++17", "-sWASM_BIGINT")


def test_make_command_wrapper_symlinks(tmp_path):
    """A copy of pywasmcross and a symlink for every wrapped tool are created,
    and compiler environment variables point at the symlinks."""
    env = make_command_wrapper_symlinks(tmp_path)

    exe = tmp_path / "pywasmcross.py"
    assert exe.is_file()
    assert os.access(exe, os.X_OK)
    assert exe.read_text() == Path(pywasmcross.__file__).read_text()

    for name in pywasmcross.SYMLINKS:
        link = tmp_path / name
        assert link.is_symlink()
        assert link.resolve() == exe

    assert env == {var: str(tmp_path / name) for name, var in SYMLINK_ENV_VARS.items()}


def test_make_command_wrapper_symlinks_replaces_stale(tmp_path):
    """Pre-existing (possibly broken) symlinks, files and directories are
    replaced."""
    (tmp_path / "cc").symlink_to(tmp_path / "does-not-exist")
    (tmp_path / "ar").write_text("not a symlink")
    (tmp_path / "cmake").mkdir()

    make_command_wrapper_symlinks(tmp_path)

    for name in ("cc", "ar", "cmake"):
        assert (tmp_path / name).resolve() == tmp_path / "pywasmcross.py"


###########################################################################
# Emscripten SDK management
###########################################################################
@pytest.mark.parametrize(
    ("output", "version"),
    [
        pytest.param(
            "emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) "
            "5.0.3 (f7a0c7e)\nCopyright (C) 2014 the Emscripten authors\n",
            "5.0.3",
            id="release",
        ),
        pytest.param(
            "emcc (Emscripten gcc/clang-like replacement) 4.0.12-git (abc)\n",
            "4.0.12",
            id="git",
        ),
        pytest.param("something else entirely\n", None, id="unparsable"),
    ],
)
def test_installed_emscripten_version(monkeypatch, output, version):
    """The version is parsed from `emcc --version`."""
    monkeypatch.setattr(
        emscripten_module.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=output),
    )

    assert installed_emscripten_version("/opt/emsdk/emcc") == version


def test_installed_emscripten_version_failure(monkeypatch):
    """An emcc that can't be run yields no version (rather than crashing)."""

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(emscripten_module.subprocess, "run", fail)

    assert installed_emscripten_version("/opt/emsdk/emcc") is None


@pytest.fixture
def fake_subprocess(monkeypatch):
    """Record the build-platform commands that the platform module runs. Each
    is "run" by calling the matching entry in `handlers` (keyed on the first
    argument's basename), if any."""
    calls = []
    handlers = {}

    def fake_clone(command, kwargs):
        if command[1] == "clone":
            (kwargs["cwd"] / command[-1] / "upstream/emscripten").mkdir(parents=True)
        return ""

    handlers["git"] = fake_clone

    def run(command, **kwargs):
        calls.append((command, kwargs))
        handler = handlers.get(Path(command[0]).name)
        stdout = handler(command, kwargs) if handler else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(emscripten_module.subprocess, "run", run)
    run.calls = calls
    run.handlers = handlers
    return run


def test_install_emsdk(tmp_path, fake_subprocess, capsys):
    """A missing SDK is cloned, installed, activated and patched inside the
    cache, using the build platform's environment; a completion marker is
    left behind."""
    prefix = _xbuildenv(tmp_path)
    root = pyodide_root(prefix)
    (root / "emsdk/patches/0001-fix.patch").touch()
    (root / "emsdk/patches/0002-fix.patch").touch()
    cache = tmp_path / "cache"
    cache.mkdir()
    emsdk_path = cache / "emsdk_5.0.3"

    assert install_emsdk("5.0.3", cache, root) == emsdk_path

    commands = [[str(arg) for arg in cmd] for cmd, _ in fake_subprocess.calls]
    assert commands == [
        [
            "git",
            "clone",
            "--depth=1",
            "https://github.com/emscripten-core/emsdk",
            "emsdk_5.0.3",
        ],
        [str(emsdk_path / "emsdk"), "install", "5.0.3"],
        [str(emsdk_path / "emsdk"), "activate", "5.0.3"],
        ["git", "apply", "--verbose", str(root / "emsdk/patches/0001-fix.patch")],
        ["git", "apply", "--verbose", str(root / "emsdk/patches/0002-fix.patch")],
    ]
    for _, kwargs in fake_subprocess.calls:
        assert kwargs["env"]["XBUILD_ENV"] == "off"
    assert fake_subprocess.calls[3][1]["env"]["GIT_DIR"] == "."
    assert fake_subprocess.calls[3][1]["cwd"] == emsdk_path / "upstream/emscripten"
    assert (emsdk_path / EMSDK_COMPLETE_MARKER).is_file()
    assert "Installing Emscripten SDK 5.0.3" in capsys.readouterr().out


def test_install_emsdk_cached(tmp_path, fake_subprocess):
    """A completed install is reused without running anything."""
    emsdk_path = tmp_path / "emsdk_5.0.3"
    emsdk_path.mkdir()
    (emsdk_path / EMSDK_COMPLETE_MARKER).touch()

    assert install_emsdk("5.0.3", tmp_path, None) == emsdk_path
    assert fake_subprocess.calls == []


def test_install_emsdk_incomplete(tmp_path, fake_subprocess, capsys):
    """An install directory without the completion marker is discarded and
    the install is retried."""
    emsdk_path = tmp_path / "emsdk_5.0.3"
    (emsdk_path / "partial").mkdir(parents=True)

    install_emsdk("5.0.3", tmp_path, None)

    assert not (emsdk_path / "partial").exists()
    assert fake_subprocess.calls[0][0][1] == "clone"
    assert "incomplete" in capsys.readouterr().out


def test_install_emsdk_failure(tmp_path, fake_subprocess):
    """A failing toolchain command is reported as a ValueError, and no
    completion marker is left behind."""

    def fail(command, kwargs):
        raise subprocess.CalledProcessError(2, command)

    fake_subprocess.handlers["emsdk"] = fail

    with pytest.raises(ValueError, match="install 5.0.3 failed with exit code 2"):
        install_emsdk("5.0.3", tmp_path, None)

    assert not (tmp_path / "emsdk_5.0.3" / EMSDK_COMPLETE_MARKER).exists()


def test_install_emsdk_missing_git(tmp_path, monkeypatch):
    """A missing `git` is reported as a ValueError."""

    def run(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(emscripten_module.subprocess, "run", run)

    with pytest.raises(ValueError, match="Could not find 'git'"):
        install_emsdk("5.0.3", tmp_path, None)


def test_emsdk_env(tmp_path, fake_subprocess):
    """The variables exported by emsdk_env.sh are captured (NUL-separated, so
    multi-line values can't confuse the parser), and only those."""
    emsdk_path = tmp_path / "emsdk_5.0.3"
    fake_subprocess.handlers["bash"] = lambda command, kwargs: "\0".join(
        [
            f"PATH={emsdk_path}/upstream/emscripten:/usr/bin",
            f"EMSDK={emsdk_path}",
            "BASH_FUNC_foo%%=() {  echo hi\n}",
            "SHLVL=2",
            "",
        ]
    )

    env = emsdk_env(emsdk_path)

    assert env == {
        "PATH": f"{emsdk_path}/upstream/emscripten:/usr/bin",
        "EMSDK": str(emsdk_path),
    }
    (command, kwargs) = fake_subprocess.calls[0]
    assert command[:2] == ["bash", "-c"]
    assert f"source {emsdk_path}/emsdk_env.sh && env -0" in command[2]
    assert kwargs["env"]["XBUILD_ENV"] == "off"


def test_emsdk_env_quotes_path(tmp_path, fake_subprocess):
    """A cache path containing shell metacharacters is quoted."""
    emsdk_path = tmp_path / "my cache" / "emsdk_5.0.3"
    fake_subprocess.handlers["bash"] = lambda command, kwargs: "PATH=/x\0"

    emsdk_env(emsdk_path)

    assert f"source '{emsdk_path}/emsdk_env.sh'" in fake_subprocess.calls[0][0][2]


def test_emsdk_env_failure(tmp_path, fake_subprocess):
    """If activation doesn't produce a PATH, that's an error."""
    fake_subprocess.handlers["bash"] = lambda command, kwargs: "FOO=bar\0"

    with pytest.raises(ValueError, match="Activating the Emscripten SDK"):
        emsdk_env(tmp_path / "emsdk_5.0.3")


def test_ensure_emscripten_matching_emcc(fake_emcc, tmp_path):
    """An emcc of the right version on PATH is used as-is."""
    assert ensure_emscripten("5.0.3", tmp_path, None) == {}


def test_ensure_emscripten_unknown_version_with_emcc(which, monkeypatch, tmp_path):
    """If the required version is unknown, whatever emcc is on PATH is used."""
    which["emcc"] = "/opt/emsdk/emcc"
    monkeypatch.setattr(
        emscripten_module, "installed_emscripten_version", lambda emcc: "1.2.3"
    )

    assert ensure_emscripten("unknown", tmp_path, None) == {}


def test_ensure_emscripten_unknown_version_without_emcc(which, tmp_path):
    """Without emcc and without a known version, there's nothing to install."""
    with pytest.raises(ValueError, match="could not be determined"):
        ensure_emscripten("unknown", tmp_path, None)


@pytest.mark.parametrize("installed", [None, "4.0.9"])
def test_ensure_emscripten_installs(which, monkeypatch, tmp_path, capsys, installed):
    """With no emcc (or the wrong one), a matching SDK is installed and its
    activation environment returned."""
    if installed is not None:
        which["emcc"] = "/opt/emsdk/emcc"
        monkeypatch.setattr(
            emscripten_module, "installed_emscripten_version", lambda emcc: installed
        )
    install = Mock(return_value=tmp_path / "emsdk_5.0.3")
    monkeypatch.setattr(emscripten_module, "install_emsdk", install)
    monkeypatch.setattr(
        emscripten_module, "emsdk_env", lambda path: {"PATH": f"{path}/bin:/usr/bin"}
    )

    env = ensure_emscripten("5.0.3", tmp_path, None)

    install.assert_called_once_with("5.0.3", tmp_path, None)
    assert env == {"PATH": f"{tmp_path / 'emsdk_5.0.3'}/bin:/usr/bin"}
    if installed is not None:
        assert "is Emscripten 4.0.9" in capsys.readouterr().out


###########################################################################
# prepare_env
###########################################################################
def test_prepare_env_missing_sysconfigdata(tmp_path, fake_emcc):
    """prepare_env() fails clearly if the sysconfigdata can't be found."""
    prefix = _xbuildenv(tmp_path)
    config = _emscripten_config(
        prefix, sysconfigdata_path=prefix / "lib" / "python3.14" / "missing.py"
    )

    with pytest.raises(ValueError, match="Could not find"):
        prepare_env(config)


def test_prepare_env_missing_abi(tmp_path, fake_emcc):
    """prepare_env() refuses to build against a Python without a Pyodide ABI."""
    prefix = _xbuildenv(tmp_path)
    build_time_vars = {
        k: v for k, v in BUILD_TIME_VARS.items() if "ABI_VERSION" not in k
    }
    config = _emscripten_config(
        prefix, sysconfigdata_path=_emscripten_sysconfigdata(prefix, build_time_vars)
    )

    with pytest.raises(ValueError, match="PYODIDE_ABI_VERSION"):
        prepare_env(config)


@pytest.mark.parametrize("via", ["sysconfigdata", "xbuildenv", "build_details"])
def test_prepare_env(tmp_path, monkeypatch, fake_emcc, no_flag_overrides, via):
    """prepare_env() creates the compiler wrappers and meson cross file, and
    returns an environment that routes compilation through them with
    localized paths."""
    wrapper_dir = tmp_path / "wrappers"
    monkeypatch.setenv(COMPILER_WRAPPER_DIR_VAR, str(wrapper_dir))
    monkeypatch.setenv("PATH", "/orig/bin")

    prefix = _xbuildenv(tmp_path)
    if via == "sysconfigdata":
        config = _emscripten_config(
            prefix, sysconfigdata_path=_emscripten_sysconfigdata(prefix)
        )
    elif via == "xbuildenv":
        config = _emscripten_config(
            prefix,
            sysconfigdata_path=_emscripten_sysconfigdata(
                prefix, layout="sysconfigdata"
            ),
        )
    else:
        config = _emscripten_config(
            prefix, build_details_path=_emscripten_build_details(prefix)
        )

    env = prepare_env(config)

    # The wrapper directory was created and populated.
    assert (wrapper_dir / "pywasmcross.py").is_file()
    assert (wrapper_dir / "cc").is_symlink()
    assert (wrapper_dir / "emscripten.meson.cross").read_text() == MESON_CROSS_FILE

    # PATH has the wrappers in front; tools are pointed at the wrappers.
    assert env["PATH"] == os.pathsep.join([str(wrapper_dir), "/orig/bin"])
    assert env[ACTIVE_COMPILER_WRAPPER_DIR_VAR] == str(wrapper_dir)
    assert env["CC"] == str(wrapper_dir / "cc")
    assert env["CXX"] == str(wrapper_dir / "c++")
    assert env["AR"] == str(wrapper_dir / "ar")
    assert env["CMAKE_EXECUTABLE"] == str(wrapper_dir / "cmake")
    assert env[MESON_CROSS_FILE_VAR] == str(wrapper_dir / "emscripten.meson.cross")
    assert env["PYODIDE_ROOT"] == str(pyodide_root(prefix))
    # The Emscripten tools run under an unpatched host Python.
    assert env["EMSDK_PYTHON"] == getattr(sys, "_base_executable", sys.executable)

    # The pywasmcross arguments are in the environment and on disk, with the
    # build-time prefix rewritten to the archive location.
    args = json.loads(env[pywasmcross.ARGS_ENV_VAR])
    assert json.loads((wrapper_dir / pywasmcross.ARGS_FILENAME).read_text()) == args
    assert args == {
        "cflags": (
            "-O2 -g0 -fPIC -fwasm-exceptions -sSUPPORT_LONGJMP=wasm "
            "-DPY_CALL_TRAMPOLINE -Oz"
        ),
        "cxxflags": "",
        "ldflags": f"-fwasm-exceptions -sSUPPORT_LONGJMP=wasm -L{prefix}/lib -Oz",
        "target_install_dir": str(prefix),
        "pythoninclude": f"{prefix}/include/python3.14",
        "exports": "pyinit",
        "abi": "2026_0",
        "PATH": "/orig/bin",
    }


def test_prepare_env_standalone_prefix(tmp_path, fake_emcc, no_flag_overrides):
    """A target Python that isn't part of an xbuildenv (e.g. `--sysconfig`
    pointing at a CPython Emscripten build) works too."""
    prefix = tmp_path / "standalone"
    config = _emscripten_config(
        prefix, sysconfigdata_path=_emscripten_sysconfigdata(prefix)
    )

    env = prepare_env(config)

    assert "PYODIDE_ROOT" not in env
    assert json.loads(env[pywasmcross.ARGS_ENV_VAR])["abi"] == "2026_0"
    shutil.rmtree(env[ACTIVE_COMPILER_WRAPPER_DIR_VAR])


def test_prepare_env_installs_emsdk(
    tmp_path, which, monkeypatch, no_flag_overrides, capsys
):
    """Without emcc, a matching SDK is installed (into the cache) and its
    environment is included -- both in the returned PATH, and in the PATH the
    wrappers fall back to."""
    monkeypatch.delenv(COMPILER_WRAPPER_DIR_VAR, raising=False)
    monkeypatch.setenv("PATH", "/orig/bin")
    prefix = _xbuildenv(tmp_path)
    cache = tmp_path / "cache"
    config = _emscripten_config(
        prefix, sysconfigdata_path=_emscripten_sysconfigdata(prefix), cache_path=cache
    )
    install = Mock(return_value=cache / "emsdk_5.0.3")
    monkeypatch.setattr(emscripten_module, "install_emsdk", install)
    monkeypatch.setattr(
        emscripten_module,
        "emsdk_env",
        lambda path: {
            "PATH": f"{path}/upstream/emscripten:/orig/bin",
            "EMSDK": str(path),
            "EMSDK_PYTHON": "/emsdk/python",
        },
    )

    env = prepare_env(config)

    install.assert_called_once_with("5.0.3", cache, pyodide_root(prefix))
    wrapper_dir = env[ACTIVE_COMPILER_WRAPPER_DIR_VAR]
    emsdk_path = f"{cache / 'emsdk_5.0.3'}/upstream/emscripten:/orig/bin"
    assert env["PATH"] == os.pathsep.join([wrapper_dir, emsdk_path])
    assert env["EMSDK"] == str(cache / "emsdk_5.0.3")
    assert env["EMSDK_PYTHON"] == "/emsdk/python"
    assert json.loads(env[pywasmcross.ARGS_ENV_VAR])["PATH"] == emsdk_path
    shutil.rmtree(wrapper_dir)


def test_prepare_env_respects_user_overrides(
    tmp_path, monkeypatch, fake_emcc, no_flag_overrides
):
    """An existing MESON_CROSS_FILE / EMSDK_PYTHON isn't overridden."""
    monkeypatch.delenv(COMPILER_WRAPPER_DIR_VAR, raising=False)
    monkeypatch.setenv(MESON_CROSS_FILE_VAR, "/my/cross.ini")
    monkeypatch.setenv("EMSDK_PYTHON", "/my/python")
    prefix = _xbuildenv(tmp_path)
    config = _emscripten_config(
        prefix, sysconfigdata_path=_emscripten_sysconfigdata(prefix)
    )

    env = prepare_env(config)

    assert env[MESON_CROSS_FILE_VAR] == "/my/cross.ini"
    assert "EMSDK_PYTHON" not in env
    shutil.rmtree(env[ACTIVE_COMPILER_WRAPPER_DIR_VAR])


def test_prepare_env_temp_wrapper_dir(tmp_path, monkeypatch, fake_emcc):
    """Without an explicit wrapper directory, a temporary one is created."""
    monkeypatch.delenv(COMPILER_WRAPPER_DIR_VAR, raising=False)
    prefix = _xbuildenv(tmp_path)
    config = _emscripten_config(
        prefix, sysconfigdata_path=_emscripten_sysconfigdata(prefix)
    )

    env = prepare_env(config)

    wrapper_dir = Path(env[ACTIVE_COMPILER_WRAPPER_DIR_VAR])
    assert wrapper_dir.name.startswith("pywasmcross-")
    assert (wrapper_dir / "cc").is_symlink()
    assert env["PATH"].startswith(str(wrapper_dir) + os.pathsep)
    shutil.rmtree(wrapper_dir)


###########################################################################
# Cross venv customization
###########################################################################
def _fake_venv(venv_path, pips=("pip", "pip3", "pip3.14")):
    """A minimal Unix-layout venv with stock pip console scripts."""
    (venv_path / "bin").mkdir(parents=True)
    (venv_path / "bin" / "python3").touch()
    for pip in pips:
        (venv_path / "bin" / pip).write_text("#!/python\nstock pip\n")


def test_install_pip_wrapper(tmp_path):
    """All pip scripts are replaced by symlinks to a launcher that runs the
    wrapper under the venv's interpreter."""
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path)

    install_pip_wrapper(venv_path)

    venv_bin = venv_path / "bin"
    wrapper = venv_bin / PIP_WRAPPER_NAME
    patched = venv_bin / PIP_PATCHED_NAME
    assert (
        wrapper.read_text()
        == (Path(pywasmcross.__file__).parent / "pip_wrapper.py").read_text()
    )
    assert os.access(patched, os.X_OK)
    assert patched.read_text() == (
        f'#!/usr/bin/env bash\nexec {venv_bin / "python3"} -s {wrapper} "$@"\n'
    )
    for pip in ("pip", "pip3", "pip3.14"):
        link = venv_bin / pip
        assert link.is_symlink()
        assert os.readlink(link) == str(patched)


def test_install_pip_wrapper_quotes_paths(tmp_path):
    """A venv path with shell metacharacters is quoted in the launcher."""
    venv_path = tmp_path / "my venv"
    _fake_venv(venv_path)

    install_pip_wrapper(venv_path)

    launcher = (venv_path / "bin" / PIP_PATCHED_NAME).read_text()
    assert f"exec '{venv_path / 'bin/python3'}' -s '{venv_path / 'bin'}/" in launcher


def test_install_pip_wrapper_idempotent(tmp_path):
    """Installing the wrapper twice (e.g., re-converting a venv) works."""
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path)

    install_pip_wrapper(venv_path)
    install_pip_wrapper(venv_path)

    venv_bin = venv_path / "bin"
    assert os.readlink(venv_bin / "pip") == str(venv_bin / PIP_PATCHED_NAME)
    assert not (venv_bin / PIP_PATCHED_NAME).is_symlink()
    assert not (venv_bin / PIP_WRAPPER_NAME).is_symlink()


def test_install_pip_wrapper_leaves_other_pip_tools(tmp_path):
    """Scripts that merely start with "pip" (pip-tools, pipx, ...) aren't
    touched."""
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, pips=("pip", "pip-compile", "pipx", "pip-audit"))

    install_pip_wrapper(venv_path)

    venv_bin = venv_path / "bin"
    assert (venv_bin / "pip").is_symlink()
    for name in ("pip-compile", "pipx", "pip-audit"):
        assert not (venv_bin / name).is_symlink()
        assert (venv_bin / name).read_text() == "#!/python\nstock pip\n"


def test_install_pip_wrapper_without_pip(tmp_path):
    """A venv created --without-pip is left alone."""
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, pips=())

    install_pip_wrapper(venv_path)

    assert sorted(p.name for p in (venv_path / "bin").iterdir()) == ["python3"]


def test_install_pip_wrapper_not_a_unix_venv(tmp_path):
    """Nothing is installed if there's no bin/python3."""
    venv_path = tmp_path / "venv"
    venv_path.mkdir()

    install_pip_wrapper(venv_path)

    assert list(venv_path.iterdir()) == []


def test_pip_wrapper_constants_in_sync():
    """The filenames the platform module uses match the ones the (standalone)
    wrapper script defines."""
    source = (Path(pywasmcross.__file__).parent / "pip_wrapper.py").read_text()
    for name, value in [
        ("PIP_WRAPPER_NAME", PIP_WRAPPER_NAME),
        ("PIP_PATCHED_NAME", PIP_PATCHED_NAME),
        ("PIP_SCRIPT_RE", emscripten_module.PIP_SCRIPT_RE.pattern),
    ]:
        match = re.search(
            rf'^{name} = (?:re\.compile\()?r?"([^"]+)"', source, re.MULTILINE
        )
        assert match, name
        assert match.group(1) == value, name


def test_install_xpython_symlink(tmp_path):
    """Inside an xbuildenv, the Pyodide interpreter is linked as xpython; the
    link is replaced if it already exists."""
    prefix = _xbuildenv(tmp_path)
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path)
    (venv_path / "bin/xpython").symlink_to("/stale")

    install_xpython_symlink(venv_path, _emscripten_config(prefix))

    assert os.readlink(venv_path / "bin/xpython") == str(
        pyodide_root(prefix) / "dist/python"
    )


def test_install_xpython_symlink_standalone(tmp_path):
    """Outside an xbuildenv, there's no interpreter to link."""
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path)

    install_xpython_symlink(venv_path, _emscripten_config(tmp_path / "standalone"))

    assert not os.path.lexists(venv_path / "bin/xpython")


def test_post_convert(tmp_path, monkeypatch):
    """post_convert installs the pip wrapper and the xpython symlink."""
    calls = []
    monkeypatch.setattr(
        emscripten_module, "install_pip_wrapper", lambda venv: calls.append("pip")
    )
    monkeypatch.setattr(
        emscripten_module,
        "install_xpython_symlink",
        lambda venv, config: calls.append("xpython"),
    )

    post_convert(tmp_path, Mock())

    assert calls == ["pip", "xpython"]


@pytest.mark.parametrize("layout", ["xbuildenv", "standalone"])
def test_convert(tmp_path, layout):
    """Converting a venv for Emscripten records the Emscripten version in the
    sysconfigdata, installs the pip wrapper, and (from an xbuildenv) links
    xpython."""
    if layout == "xbuildenv":
        prefix = _xbuildenv(tmp_path)
        sysconfigdata_path = _emscripten_sysconfigdata(prefix, layout="sysconfigdata")
    else:
        prefix = tmp_path / "standalone"
        sysconfigdata_path = _emscripten_sysconfigdata(prefix)
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path)
    site_packages = venv_path / "lib" / "python3.14" / "site-packages"
    site_packages.mkdir(parents=True)
    (venv_path / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.14.2\n")

    CrossVenvConfig(
        platform=None,
        arch=None,
        build_details_path=None,
        sysconfigdata_path=sysconfigdata_path,
        cache_path=None,
    ).convert(venv_path)

    assert (venv_path / "bin" / "pip").is_symlink()
    assert (venv_path / "bin" / PIP_WRAPPER_NAME).is_file()
    localized = (site_packages / sysconfigdata_path.name).read_text()
    assert "'EMSCRIPTEN_VERSION': '5.0.3'" in localized
    assert (venv_path / "bin/xpython").is_symlink() == (layout == "xbuildenv")
    cross_target = (
        site_packages / "_cross_emscripten_wasm32_emscripten.py"
    ).read_text()
    assert 'release="5.0.3"' in cross_target


###########################################################################
# Testbed
###########################################################################
def test_packages_path(tmp_path):
    """Dependencies are installed into the cross venv's own site-packages."""
    series = f"{sys.version_info.major}.{sys.version_info.minor}"

    assert (
        packages_path(tmp_path) == tmp_path / f"venv/lib/python{series}/site-packages"
    )


def test_setup_testbed(tmp_path, which):
    """Sources are staged into `src`."""
    which["node"] = "/usr/bin/node"
    prefix = _xbuildenv(tmp_path)
    (tmp_path / "app").mkdir()
    (tmp_path / "app/main.py").write_text("print('hi')\n")
    (tmp_path / "test_x.py").write_text("")

    setup_testbed(prefix, tmp_path / "work", [tmp_path / "app", tmp_path / "test_x.py"])

    assert (tmp_path / "work/src/app/main.py").read_text() == "print('hi')\n"
    assert (tmp_path / "work/src/test_x.py").is_file()


def test_setup_testbed_requirements(tmp_path, which):
    """The testbed needs an xbuildenv (for the interpreter) and node."""
    with pytest.raises(RuntimeError, match="isn't part of a Pyodide"):
        setup_testbed(tmp_path / "standalone", tmp_path / "work", [])

    prefix = _xbuildenv(tmp_path)
    with pytest.raises(RuntimeError, match="requires `node`"):
        setup_testbed(prefix, tmp_path / "work", [])


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param([], ["-m", "test"], id="default"),
        pytest.param(["-c", "print(1)"], ["-c", "print(1)"], id="explicit"),
    ],
)
def test_run_testbed(tmp_path, fake_subprocess, args, expected):
    """The xpython symlink in the venv is run against the staged sources."""
    assert run_testbed(tmp_path, args, verbose=0) == 0

    ((command, kwargs),) = fake_subprocess.calls
    assert command == [str(tmp_path / "venv/bin/xpython"), *expected]
    assert kwargs["cwd"] == tmp_path / "src"
    assert kwargs["env"]["XBUILD_ENV"] == "off"
