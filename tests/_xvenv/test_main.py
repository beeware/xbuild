import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from xvenv.__main__ import main


@pytest.fixture
def venv_path(tmp_path):
    return tmp_path / "x-venv"


@pytest.fixture
def mock_config():
    return Mock()


@pytest.fixture
def mock_CrossVenvConfig(monkeypatch, mock_config):
    CrossVenvConfig = Mock(return_value=mock_config)
    CrossVenvConfig.from_current_env.return_value = mock_config
    monkeypatch.setattr("xvenv.__main__.CrossVenvConfig", CrossVenvConfig)
    return CrossVenvConfig


@pytest.mark.parametrize(
    ("args", "error"),
    [
        pytest.param(
            (
                "--sysconfig",
                "/path/to/sysconfig.py",
                "--build-details",
                "/path/to/build-details.json",
            ),
            "not allowed with argument",
            id="sysconfig-and-build-details",
        ),
        pytest.param(
            ("--sysconfig", "/path/to/sysconfig.py", "--platform", "ios"),
            "not allowed with argument",
            id="sysconfig-and-platform",
        ),
        pytest.param(
            ("--build-details", "/path/to/build-details.json", "--platform", "android"),
            "not allowed with argument",
            id="build-details-and-platform",
        ),
        pytest.param(
            ("--sysconfig", "/path/to/sysconfig.py", "--arch", "arm64"),
            "--arch option also requires --platform",
            id="sysconfig-and-arch",
        ),
        pytest.param(
            ("--cache", "/path/to/cache", "--sysconfig", "/path/to/sysconfig.py"),
            "--cache option also requires --platform",
            id="sysconfig-and-cache",
        ),
        pytest.param(
            ("--cache", "/path/to/cache", "--archive", "/path/to/archive"),
            "not allowed with argument",
            id="cache-and-archive",
        ),
        pytest.param(
            ("--archive", "/path/to/archive", "--sysconfig", "/path/to/sysconfig.py"),
            "--archive option also requires --platform",
            id="sysconfig-and-archive",
        ),
    ],
)
def test_invalid_args(args, error, tmp_path, capsys):
    """Invalid flag combinations raise errors."""
    with pytest.raises(SystemExit) as excinfo:
        main([*args, str(tmp_path / "x-venv")])

    assert excinfo.value.code == 2
    assert error in capsys.readouterr().err


@pytest.mark.parametrize(
    ("args", "already_exists", "config_kwargs", "with_pip"),
    [
        pytest.param(
            ["--platform", "android"],
            False,
            {
                "platform": "android",
            },
            True,
            id="platform",
        ),
        pytest.param(
            ["--platform", "android", "--without-pip"],
            False,
            {
                "platform": "android",
            },
            False,
            id="no-pip",
        ),
        pytest.param(
            ["--platform", "android", "--arch", "arm64_v8a"],
            False,
            {
                "platform": "android",
                "arch": "arm64_v8a",
            },
            True,
            id="platform-with-arch",
        ),
        pytest.param(
            ["--platform", "android", "--cache", "path/to/cache"],
            False,
            {
                "platform": "android",
                "cache_path": Path("path/to/cache"),
            },
            True,
            id="cache",
        ),
        pytest.param(
            ["--platform", "android", "--archive", "path/to/archive"],
            False,
            {
                "platform": "android",
                "archive_path": Path("path/to/archive"),
            },
            True,
            id="archive",
        ),
        pytest.param(
            ["--build-details", "path/to/build-config.json"],
            True,
            {"build_details_path": Path("path/to/build-config.json")},
            True,
            id="build-details",
        ),
        pytest.param(
            ["--sysconfig", "path/to/sysconfigdata.py"],
            False,
            {"sysconfigdata_path": Path("path/to/sysconfigdata.py")},
            True,
            id="sysconfig",
        ),
    ],
)
def test_valid_args(
    venv_path,
    mock_CrossVenvConfig,
    mock_config,
    args,
    already_exists,
    config_kwargs,
    with_pip,
):
    """Verify some valid argument cases."""
    # If the venv should already exist, create it
    if already_exists:
        venv_path.mkdir()

    main([*args, str(venv_path)])

    kwargs = {
        "platform": None,
        "arch": None,
        "build_details_path": None,
        "sysconfigdata_path": None,
        "cache_path": None,
        "archive_path": None,
    }
    kwargs.update(config_kwargs)
    mock_CrossVenvConfig.assert_called_once_with(**kwargs)
    mock_config.create.assert_called_once_with(venv_path, with_pip=with_pip)


@pytest.fixture
def native_env(monkeypatch):
    monkeypatch.delattr(sys, "cross_compiling", raising=False)


@pytest.fixture
def cross_env(monkeypatch):
    monkeypatch.setattr(sys, "cross_compiling", True, raising=False)


def test_no_config_outside_cross_env(native_env, venv_path, capsys):
    """Outside a cross env, a configuration source is required."""
    with pytest.raises(SystemExit) as excinfo:
        main([str(venv_path)])

    assert excinfo.value.code == 2
    assert (
        "One of the arguments --build-details, --sysconfig, or --platform is required"
        in capsys.readouterr().err
    )


def test_no_config_in_cross_env(
    cross_env, venv_path, mock_CrossVenvConfig, mock_config
):
    """Inside a cross env, the current environment's config is used if no
    configuration source is given."""
    main([str(venv_path)])

    mock_CrossVenvConfig.assert_not_called()
    mock_CrossVenvConfig.from_current_env.assert_called_once_with()
    mock_config.create.assert_called_once_with(venv_path, with_pip=True)


def test_explicit_config_in_cross_env(
    cross_env, venv_path, mock_CrossVenvConfig, mock_config
):
    """Inside a cross env, an explicit configuration source takes precedence."""
    main(["--platform", "ios", str(venv_path)])

    mock_CrossVenvConfig.from_current_env.assert_not_called()
    mock_CrossVenvConfig.assert_called_once_with(
        platform="ios",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
        archive_path=None,
    )
    mock_config.create.assert_called_once_with(venv_path, with_pip=True)


def test_current_env_error(cross_env, venv_path, mock_CrossVenvConfig, capsys):
    """An error determining the current env's configuration is surfaced."""
    mock_CrossVenvConfig.from_current_env.side_effect = ValueError("no record")

    with pytest.raises(SystemExit) as excinfo:
        main([str(venv_path)])

    assert excinfo.value.code == 1
    assert "no record" in capsys.readouterr().err
