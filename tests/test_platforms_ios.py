import sys

from xvenv.platforms.ios import VALID_ARCHES, config_path, download_url


def test_valid_arches():
    assert VALID_ARCHES == [
        "arm64_iphonesimulator",
        "x86_64_iphonesimulator",
        "arm64_iphoneos",
    ]


def test_download_url_314_plus():
    version_info = sys.version_info.__replace__(
        major=3, minor=15, micro=0, releaselevel="candidate", serial=2
    )

    url = download_url("3.15.0rc2", version_info)

    assert url == (
        "https://www.python.org/ftp/python/3.15.0rc2/"
        "python-3.15.0rc2-iOS-XCframework.tar.gz"
    )


def test_download_url_pre_314_is_placeholder():
    version_info = sys.version_info.__replace__(
        major=3, minor=13, micro=7, releaselevel="final", serial=0
    )

    url = download_url("3.13.7", version_info)

    assert url.startswith("https://TODO.example/")


def test_config_path_314_plus_simulator_arm64(tmp_path):
    version_info = sys.version_info.__replace__(
        major=3, minor=15, micro=0, releaselevel="final", serial=0
    )

    path = config_path(tmp_path, version_info, "arm64_iphonesimulator")

    assert path == (
        tmp_path
        / "Python.xcframework"
        / "ios-arm64_x86_64-simulator"
        / "lib-arm64"
        / "python3.15"
        / "build-details.json"
    )


def test_config_path_314_plus_simulator_x86_64(tmp_path):
    version_info = sys.version_info.__replace__(
        major=3, minor=15, micro=0, releaselevel="final", serial=0
    )

    path = config_path(tmp_path, version_info, "x86_64_iphonesimulator")

    assert path == (
        tmp_path
        / "Python.xcframework"
        / "ios-arm64_x86_64-simulator"
        / "lib-x86_64"
        / "python3.15"
        / "build-details.json"
    )


def test_config_path_314_plus_device_arm64(tmp_path):
    version_info = sys.version_info.__replace__(
        major=3, minor=15, micro=0, releaselevel="final", serial=0
    )

    path = config_path(tmp_path, version_info, "arm64_iphoneos")

    assert path == (
        tmp_path
        / "Python.xcframework"
        / "ios-arm64"
        / "lib-arm64"
        / "python3.15"
        / "build-details.json"
    )


def test_config_path_pre_314_uses_legacy_sysconfigdata(tmp_path):
    version_info = sys.version_info.__replace__(
        major=3, minor=13, micro=7, releaselevel="final", serial=0
    )

    path = config_path(tmp_path, version_info, "arm64_iphonesimulator")

    assert path == (
        tmp_path
        / "Python.xcframework"
        / "ios-arm64_x86_64-simulator"
        / "lib-arm64"
        / "python3.13"
        / "_sysconfigdata__ios_arm64-iphonesimulator.py"
    )
