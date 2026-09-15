import sys

import pytest

from xvenv.platforms.android import config_path, download_url


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
    version_info = sys.version_info.__replace__(**version_details)

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
    version_info = sys.version_info.__replace__(**version_details)

    actual_config_path = config_path(tmp_path, version_info, arch)

    assert actual_config_path == tmp_path / path
