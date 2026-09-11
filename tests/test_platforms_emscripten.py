import pytest

from xvenv.platforms.emscripten import VALID_ARCHES, config_path, download_url


def test_valid_arches():
    assert VALID_ARCHES == []


def test_download_url_not_implemented():
    with pytest.raises(NotImplementedError):
        download_url("3.15.0", "wasm32")


def test_config_path_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError):
        config_path(tmp_path, None, "wasm32")
