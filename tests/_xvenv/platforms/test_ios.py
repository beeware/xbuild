import os
import sys
from unittest.mock import Mock

import pytest

from xvenv.convert import CrossVenvConfig
from xvenv.platforms.ios import config_path, download_url, prepare_env

from ...utils import VersionInfo


@pytest.mark.parametrize(
    ("version_details", "arch", "url"),
    [
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://www.python.org/ftp/python/3.15.7/"
                "python-3.15.7-iOS-XCframework.tar.gz"
            ),
            id="3.15.7-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64-iphonesimulator",
            (
                "https://www.python.org/ftp/python/3.15.7/"
                "python-3.15.7-iOS-XCframework.tar.gz"
            ),
            id="3.15.7-x86_64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphoneos",
            (
                "https://www.python.org/ftp/python/3.15.7/"
                "python-3.15.7-iOS-XCframework.tar.gz"
            ),
            id="3.15.7-arm64-iphoneos",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "arm64-iphonesimulator",
            (
                "https://www.python.org/ftp/python/3.15.0/"
                "python-3.15.0rc2-iOS-XCframework.tar.gz"
            ),
            id="3.15.0rc2-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://github.com/beeware/Python-Apple-support/releases/download/"
                "3.14-b11/Python-3.14-iOS-support.b11.tar.gz"
            ),
            id="3.14.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://github.com/beeware/Python-Apple-support/releases/download/"
                "3.13-b15/Python-3.13-iOS-support.b15.tar.gz"
            ),
            id="3.13.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 12,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://github.com/beeware/Python-Apple-support/releases/download/"
                "3.12-b10/Python-3.12-iOS-support.b10.tar.gz"
            ),
            id="3.12.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 11,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://github.com/beeware/Python-Apple-support/releases/download/"
                "3.11-b10/Python-3.11-iOS-support.b10.tar.gz"
            ),
            id="3.11.10-arm64-iphonesimulator",
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
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.15/build-details.json"
            ),
            id="3.15.7-x86_64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-x86_64/"
                "python3.15/build-details.json"
            ),
            id="3.15.7-x86_64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphoneos",
            "Python.xcframework/ios-arm64/lib-arm64/python3.15/build-details.json",
            id="3.15.7-arm64-iphoneos",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.15/build-details.json"
            ),
            id="3.15.0rc2-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.14/build-details.json"
            ),
            id="3.14.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.13/_sysconfigdata__ios_arm64-iphonesimulator.py"
            ),
            id="3.13.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-x86_64/"
                "python3.13/_sysconfigdata__ios_x86_64-iphonesimulator.py"
            ),
            id="3.13.10-x86_64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphoneos",
            (
                "Python.xcframework/ios-arm64/lib-arm64/"
                "python3.13/_sysconfigdata__ios_arm64-iphoneos.py"
            ),
            id="3.13.10-arm64-iphoneos",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 12,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.12/_sysconfigdata__ios_arm64-iphonesimulator.py"
            ),
            id="3.12.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 11,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.11/_sysconfigdata__ios_arm64-iphonesimulator.py"
            ),
            id="3.11.10-arm64-iphonesimulator",
        ),
    ],
)
def test_config_path(tmp_path, version_details, arch, path):
    """The location of the iOS configuration path can be determined."""
    version_info = VersionInfo(**version_details)

    actual_config_path = config_path(tmp_path, version_info, arch)

    assert actual_config_path == tmp_path / path


def _ios_config(arch, archive_path):
    return CrossVenvConfig(
        platform="ios",
        arch=arch,
        archive_path=archive_path,
        platform_module=None,
        build_details_path=None,
        sysconfigdata_path=archive_path / "fake-sysconfigdata.py",
    )


def test_prepare_env_simulator_slice(tmp_path, monkeypatch):
    """prepare_env() selects the simulator slice's bin/ dir for an
    -iphonesimulator arch, and replaces PATH entirely."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        "xvenv.platforms.ios.shutil.which", Mock(return_value="/usr/bin/xcrun")
    )
    monkeypatch.setattr(sys, "executable", "/venv/bin/python3")

    config = _ios_config("arm64-iphonesimulator", tmp_path)

    env = prepare_env(config)

    expected_slice_bin = (
        tmp_path / "Python.xcframework" / "ios-arm64_x86_64-simulator" / "bin"
    )
    assert env["PATH"] == os.pathsep.join(
        [
            "/venv/bin",
            str(expected_slice_bin),
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
            "/Library/Apple/usr/bin",
        ]
    )


def test_prepare_env_device_slice(tmp_path, monkeypatch):
    """prepare_env() selects the device slice's bin/ dir for an
    -iphoneos arch."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(
        "xvenv.platforms.ios.shutil.which", Mock(return_value="/usr/bin/xcrun")
    )
    monkeypatch.setattr(sys, "executable", "/venv/bin/python3")

    config = _ios_config("arm64-iphoneos", tmp_path)

    env = prepare_env(config)

    expected_slice_bin = tmp_path / "Python.xcframework" / "ios-arm64" / "bin"
    assert str(expected_slice_bin) in env["PATH"]


def test_prepare_env_requires_macos(tmp_path, monkeypatch):
    """prepare_env() raises ValueError when not running on macOS."""
    monkeypatch.setattr(sys, "platform", "linux")

    config = _ios_config("arm64-iphonesimulator", tmp_path)

    with pytest.raises(ValueError, match="requires macOS"):
        prepare_env(config)


def test_prepare_env_requires_xcrun(tmp_path, monkeypatch):
    """prepare_env() raises ValueError when Xcode command-line tools
    (xcrun) are not available."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr("xvenv.platforms.ios.shutil.which", Mock(return_value=None))

    config = _ios_config("arm64-iphonesimulator", tmp_path)

    with pytest.raises(ValueError, match="Xcode command-line tools"):
        prepare_env(config)
