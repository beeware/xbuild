from unittest.mock import Mock

import pytest

from xvenv.api import create_cross_venv


@pytest.fixture
def mock_deps(monkeypatch, tmp_path):
    # config_path must live under the *resolved cache dir* (tmp_path /
    # "cache"), not some unrelated directory -- create_cross_venv() derives
    # archive_dir by walking config_path back up to its ancestor directly
    # under resolved_cache_dir, so config_path.relative_to(resolved_cache_dir)
    # must actually succeed.
    cache_dir = tmp_path / "cache"
    archive_dir = cache_dir / "python-3.14.7-aarch64-linux-android"
    config_path = archive_dir / "prefix" / "lib" / "python3.14" / "build-details.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}")

    mocks = {
        "create": Mock(),
        "resolve_cache_dir": Mock(return_value=cache_dir),
        "resolve_arch": Mock(return_value="aarch64"),
        "fetch_python": Mock(return_value=(config_path, True)),
        "convert_venv": Mock(return_value="android aarch64-linux-android"),
    }
    monkeypatch.setattr("xvenv.api.venv.create", mocks["create"])
    monkeypatch.setattr("xvenv.api.resolve_cache_dir", mocks["resolve_cache_dir"])
    monkeypatch.setattr("xvenv.api.resolve_arch", mocks["resolve_arch"])
    monkeypatch.setattr("xvenv.api.fetch_python", mocks["fetch_python"])
    monkeypatch.setattr("xvenv.api.convert_venv", mocks["convert_venv"])
    mocks["cache_dir"] = cache_dir
    mocks["archive_dir"] = archive_dir
    return mocks


def test_creates_venv_when_missing(tmp_path, mock_deps):
    """create_cross_venv() creates the venv if it doesn't exist, and returns
    the description + archive dir."""
    venv_path = tmp_path / "x-venv"

    result = create_cross_venv(venv_path, "android", None, None)

    mock_deps["create"].assert_called_once_with(venv_path, with_pip=True)
    mock_deps["resolve_cache_dir"].assert_called_once_with(None)
    mock_deps["resolve_arch"].assert_called_once_with("android", None)
    mock_deps["fetch_python"].assert_called_once_with(
        "android", "aarch64", mock_deps["cache_dir"]
    )
    mock_deps["convert_venv"].assert_called_once()
    assert result.description == "android aarch64-linux-android"
    assert result.archive_dir == mock_deps["archive_dir"]


def test_reuses_existing_venv(tmp_path, mock_deps):
    """create_cross_venv() does not re-create an already-existing venv."""
    venv_path = tmp_path / "x-venv"
    venv_path.mkdir()

    create_cross_venv(venv_path, "android", None, None)

    mock_deps["create"].assert_not_called()


def test_without_pip_passthrough(tmp_path, mock_deps):
    """with_pip=False is passed through to venv.create()."""
    venv_path = tmp_path / "x-venv"

    create_cross_venv(venv_path, "android", None, None, with_pip=False)

    mock_deps["create"].assert_called_once_with(venv_path, with_pip=False)


def test_archive_dir_derived_from_config_path(tmp_path, mock_deps):
    """archive_dir is the top-level extracted directory, not the config
    file's immediate parent -- i.e. it walks back up to the directory
    fetch_python() extracted the archive into."""
    venv_path = tmp_path / "x-venv"

    result = create_cross_venv(venv_path, "android", None, None)

    # The fixture's config_path is archive_dir/prefix/lib/python3.14/build-details.json
    assert result.archive_dir == mock_deps["archive_dir"]
