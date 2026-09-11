import sys

from xvenv.platforms.android import VALID_ARCHES, config_path, download_url


def test_valid_arches():
    assert VALID_ARCHES == ["aarch64", "x86_64"]


def test_download_url_314_plus():
    version_info = sys.version_info.__replace__(
        major=3, minor=14, micro=7, releaselevel="final", serial=0
    )

    url = download_url("3.14.7", "aarch64", version_info)

    assert url == (
        "https://www.python.org/ftp/python/3.14.7/"
        "python-3.14.7-aarch64-linux-android.tar.gz"
    )


def test_download_url_pre_314_is_placeholder():
    version_info = sys.version_info.__replace__(
        major=3, minor=13, micro=7, releaselevel="final", serial=0
    )

    url = download_url("3.13.7", "aarch64", version_info)

    assert url.startswith("https://TODO.example/")


def test_config_path_314_plus(tmp_path):
    version_info = sys.version_info.__replace__(
        major=3, minor=14, micro=7, releaselevel="final", serial=0
    )

    path = config_path(tmp_path, version_info, "aarch64")

    assert path == (tmp_path / "prefix" / "lib" / "python3.14" / "build-details.json")


def test_config_path_pre_314_uses_legacy_sysconfigdata(tmp_path):
    version_info = sys.version_info.__replace__(
        major=3, minor=13, micro=7, releaselevel="final", serial=0
    )

    path = config_path(tmp_path, version_info, "x86_64")

    assert path == (
        tmp_path
        / "prefix"
        / "lib"
        / "python3.13"
        / "_sysconfigdata__android_x86_64-linux-android.py"
    )
