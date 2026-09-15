import sys

import pytest

from xvenv.platforms.emscripten import config_path, download_url


@pytest.mark.parametrize(
    ("version_details", "url"),
    [
        (
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "unknown",
        ),
        (
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "unknown",
        ),
    ],
)
def test_download_url(version_details, url):
    """The download URL can be constructed from the version and architecture."""
    version_info = sys.version_info.__replace__(**version_details)

    with pytest.raises(NotImplementedError):
        actual_url = download_url(version_info, "wasm32")  # noqa: F841

    # assert actual_url == url


@pytest.mark.parametrize(
    ("version_details", "path"),
    [
        (
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "unknown",
        ),
        (
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "unknown",
        ),
    ],
)
def test_config_path(tmp_path, version_details, path):
    """The location of the Emscripten configuration path can be determined."""
    version_info = sys.version_info.__replace__(**version_details)

    with pytest.raises(NotImplementedError):
        actual_config_path = config_path(tmp_path, version_info, "wasm32")  # noqa: F841

    # assert actual_config_path == tmp_path / path
