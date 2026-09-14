import sys

import pytest

from xvenv.platforms.ios import config_path, download_url


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
    version_info = sys.version_info.__replace__(**version_details)

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
    version_info = sys.version_info.__replace__(**version_details)

    actual_config_path = config_path(tmp_path, version_info, arch)

    assert actual_config_path == tmp_path / path
