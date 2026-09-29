import json
import stat
from pathlib import Path

import pytest

from xvenv.convert import CrossVenvConfig
from xvenv.platforms.android import config_path, download_url, prepare_env

from ...utils import VersionInfo


@pytest.mark.parametrize(
    ("version_details", "arch", "url"),
    [
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            (
                "https://www.python.org/ftp/python/3.14.7/"
                "python-3.14.7-aarch64-linux-android.tar.gz"
            ),
            id="3.14.7-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            (
                "https://www.python.org/ftp/python/3.14.7/"
                "python-3.14.7-x86_64-linux-android.tar.gz"
            ),
            id="3.14.7-x86_64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "aarch64",
            (
                "https://www.python.org/ftp/python/3.15.0/"
                "python-3.15.0rc2-aarch64-linux-android.tar.gz"
            ),
            id="3.15.0rc2-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            (
                "https://repo.maven.apache.org/maven2/com/chaquo/python/python/"
                "3.13.15/python-3.13.15-aarch64-linux-android.tar.gz"
            ),
            id="3.13.11-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            (
                "https://repo.maven.apache.org/maven2/com/chaquo/python/python/"
                "3.13.15/python-3.13.15-x86_64-linux-android.tar.gz"
            ),
            id="3.13.11-x86_64",
        ),
    ],
)
def test_download_url(version_details, arch, url):
    """The download URL can be constructed from the version and architecture."""
    version_info = VersionInfo(**version_details)

    actual_url = download_url(version_info, arch)

    assert actual_url == url


@pytest.mark.parametrize(
    ("version_details", "arch", "path"),
    [
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            "prefix/lib/python3.14/build-details.json",
            id="3.14.7-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            "prefix/lib/python3.14/build-details.json",
            id="3.14.7-x86_64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "aarch64",
            "prefix/lib/python3.15/build-details.json",
            id="3.15.0rc2-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            "prefix/lib/python3.13/_sysconfigdata__android_aarch64-linux-android.py",
            id="3.13.10-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            "prefix/lib/python3.13/_sysconfigdata__android_x86_64-linux-android.py",
            id="3.13.10-x86_64",
        ),
    ],
)
def test_config_path(tmp_path, version_details, arch, path):
    """The location of the Android configuration path can be determined."""
    version_info = VersionInfo(**version_details)

    actual_config_path = config_path(tmp_path, version_info, arch)

    assert actual_config_path == tmp_path / path


def _make_ndk(
    android_home: Path,
    ndk_version: str,
    prebuilt_dir_name: str,
    clang_prefix: str,
    api_level: int,
) -> None:
    """Build a fake NDK layout under android_home/ndk/<ndk_version>/...
    with the toolchain binaries prepare_env() looks for."""
    toolchain = (
        android_home
        / "ndk"
        / ndk_version
        / "toolchains"
        / "llvm"
        / "prebuilt"
        / prebuilt_dir_name
        / "bin"
    )
    toolchain.mkdir(parents=True)
    for name in [
        f"{clang_prefix}{api_level}-clang",
        f"{clang_prefix}{api_level}-clang++",
        "llvm-ar",
        "llvm-as",
        "ld",
        "llvm-nm",
        "llvm-ranlib",
        "llvm-readelf",
        "llvm-strip",
    ]:
        tool = toolchain / name
        tool.write_text("#!/bin/sh\n")
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)


def _write_android_env_sh(archive_path: Path, ndk_version: str) -> None:
    (archive_path / "android-env.sh").write_text(f"ndk_version={ndk_version}\n")


def _android_config(
    archive_path,
    sysconfigdata_path=None,
    build_details_path=None,
    arch="aarch64-linux-android",
):
    return CrossVenvConfig(
        platform="android",
        arch=arch,
        archive_path=archive_path,
        platform_module=None,
        build_details_path=build_details_path,
        sysconfigdata_path=sysconfigdata_path,
    )


def test_prepare_env_success_via_sysconfigdata(tmp_path, monkeypatch):
    """A full happy-path run using sysconfigdata_path to supply the API
    level: CC/AR/etc. point at the right files, CFLAGS/LDFLAGS are
    assembled, and PKG_CONFIG/PKG_CONFIG_LIBDIR are set because prefix/
    exists."""
    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    android_home = tmp_path / "android-sdk"
    _make_ndk(
        android_home, "27.3.13750724", "darwin-x86_64", "aarch64-linux-android", 24
    )
    _write_android_env_sh(archive_path, "27.3.13750724")
    monkeypatch.setenv("ANDROID_HOME", str(android_home))

    sysconfigdata_path = (
        archive_path
        / "prefix"
        / "lib"
        / "python3.13"
        / "_sysconfigdata__android_aarch64-linux-android.py"
    )
    sysconfigdata_path.parent.mkdir(parents=True)
    sysconfigdata_path.write_text("build_time_vars = {'ANDROID_API_LEVEL': 24}")

    prefix = archive_path / "prefix"
    prefix.mkdir(exist_ok=True)

    config = _android_config(archive_path, sysconfigdata_path=sysconfigdata_path)

    env = prepare_env(config)

    toolchain_bin = (
        android_home
        / "ndk"
        / "27.3.13750724"
        / "toolchains"
        / "llvm"
        / "prebuilt"
        / "darwin-x86_64"
        / "bin"
    )
    assert env["CC"] == str(toolchain_bin / "aarch64-linux-android24-clang")
    assert env["CXX"] == str(toolchain_bin / "aarch64-linux-android24-clang") + "++"
    assert env["AR"] == str(toolchain_bin / "llvm-ar")
    assert "-D__BIONIC_NO_PAGE_SIZE_MACRO" in env["CFLAGS"]
    assert "-Wl,--no-undefined" in env["LDFLAGS"]
    assert env["PKG_CONFIG"] == "pkg-config --define-prefix"
    assert env["PKG_CONFIG_LIBDIR"] == f"{prefix.resolve()}/lib/pkgconfig"
    assert "CPU_COUNT" in env
    assert "PATH" not in env


def test_prepare_env_success_via_build_details(tmp_path, monkeypatch):
    """The same happy path, but using build_details_path to supply the API
    level instead of sysconfigdata_path."""
    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    android_home = tmp_path / "android-sdk"
    _make_ndk(
        android_home, "27.3.13750724", "linux-x86_64", "aarch64-linux-android", 24
    )
    _write_android_env_sh(archive_path, "27.3.13750724")
    monkeypatch.setenv("ANDROID_HOME", str(android_home))

    build_details_path = (
        archive_path / "prefix" / "lib" / "python3.14" / "build-details.json"
    )
    build_details_path.parent.mkdir(parents=True)
    build_details_path.write_text(json.dumps({"platform": "android-24-arm64_v8a"}))

    config = _android_config(archive_path, build_details_path=build_details_path)

    env = prepare_env(config)

    assert "aarch64-linux-android24-clang" in env["CC"]


def test_prepare_env_no_prefix_omits_pkg_config(tmp_path, monkeypatch):
    """If prefix/ doesn't exist in the archive, PKG_CONFIG/
    PKG_CONFIG_LIBDIR are not set, and CFLAGS/LDFLAGS have no -I/-L."""
    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    android_home = tmp_path / "android-sdk"
    _make_ndk(
        android_home, "27.3.13750724", "darwin-x86_64", "aarch64-linux-android", 24
    )
    _write_android_env_sh(archive_path, "27.3.13750724")
    monkeypatch.setenv("ANDROID_HOME", str(android_home))

    # Note: sysconfigdata_path is placed directly under archive_path (not
    # under archive_path/prefix/...) so that no prefix/ directory is
    # incidentally created as a side effect of mkdir(parents=True) above --
    # this test specifically exercises the no-prefix/ branch.
    sysconfigdata_path = (
        archive_path / "_sysconfigdata__android_aarch64-linux-android.py"
    )
    sysconfigdata_path.write_text("build_time_vars = {'ANDROID_API_LEVEL': 24}")

    config = _android_config(archive_path, sysconfigdata_path=sysconfigdata_path)

    env = prepare_env(config)

    assert "PKG_CONFIG" not in env
    assert "PKG_CONFIG_LIBDIR" not in env
    assert "-I" not in env["CFLAGS"]
    assert "-L" not in env["LDFLAGS"]


def test_prepare_env_arm_triplet_substitution(tmp_path, monkeypatch):
    """arm-linux-androideabi host gets the armv7a-linux-androideabi clang
    triplet substitution and extra CFLAGS."""
    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    android_home = tmp_path / "android-sdk"
    _make_ndk(
        android_home, "27.3.13750724", "darwin-x86_64", "armv7a-linux-androideabi", 21
    )
    _write_android_env_sh(archive_path, "27.3.13750724")
    monkeypatch.setenv("ANDROID_HOME", str(android_home))

    sysconfigdata_path = (
        archive_path
        / "prefix"
        / "lib"
        / "python3.13"
        / "_sysconfigdata__android_arm-linux-androideabi.py"
    )
    sysconfigdata_path.parent.mkdir(parents=True)
    sysconfigdata_path.write_text("build_time_vars = {'ANDROID_API_LEVEL': 21}")

    config = _android_config(
        archive_path,
        sysconfigdata_path=sysconfigdata_path,
        arch="arm-linux-androideabi",
    )

    env = prepare_env(config)

    assert "armv7a-linux-androideabi21-clang" in env["CC"]
    assert "-march=armv7-a -mthumb" in env["CFLAGS"]


def test_prepare_env_missing_android_home(tmp_path, monkeypatch):
    """ANDROID_HOME not set raises a clear ValueError."""
    monkeypatch.delenv("ANDROID_HOME", raising=False)

    config = _android_config(tmp_path, sysconfigdata_path=tmp_path / "fake.py")

    with pytest.raises(ValueError, match="ANDROID_HOME"):
        prepare_env(config)


def test_prepare_env_missing_android_env_sh(tmp_path, monkeypatch):
    """A missing android-env.sh in the archive raises a clear ValueError."""
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "android-sdk"))
    sysconfigdata_path = (
        tmp_path
        / "prefix"
        / "lib"
        / "python3.13"
        / "_sysconfigdata__android_aarch64-linux-android.py"
    )
    sysconfigdata_path.parent.mkdir(parents=True)
    sysconfigdata_path.write_text("build_time_vars = {'ANDROID_API_LEVEL': 24}")

    config = _android_config(tmp_path, sysconfigdata_path=sysconfigdata_path)

    with pytest.raises(ValueError, match="Could not find"):
        prepare_env(config)


def test_prepare_env_ndk_not_installed(tmp_path, monkeypatch):
    """The required NDK version not being installed under
    $ANDROID_HOME/ndk/ raises a ValueError naming the exact expected
    version and path (fail-fast, no auto-install)."""
    android_home = tmp_path / "android-sdk"
    android_home.mkdir()
    monkeypatch.setenv("ANDROID_HOME", str(android_home))

    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    _write_android_env_sh(archive_path, "27.3.13750724")

    sysconfigdata_path = (
        archive_path
        / "prefix"
        / "lib"
        / "python3.13"
        / "_sysconfigdata__android_aarch64-linux-android.py"
    )
    sysconfigdata_path.parent.mkdir(parents=True)
    sysconfigdata_path.write_text("build_time_vars = {'ANDROID_API_LEVEL': 24}")

    config = _android_config(archive_path, sysconfigdata_path=sysconfigdata_path)

    with pytest.raises(ValueError, match="27.3.13750724"):
        prepare_env(config)
