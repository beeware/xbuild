from pathlib import Path
from unittest.mock import Mock

import pytest

from xvenv.__main__ import main


@pytest.fixture
def venv_path(tmp_path):
    return tmp_path / "x-venv"


@pytest.fixture
def mock_create_cross_venv(monkeypatch):
    create_cross_venv = Mock()
    monkeypatch.setattr("xvenv.__main__.create_cross_venv", create_cross_venv)
    return create_cross_venv


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
            "--arch requires --platform",
            id="sysconfig-and-arch",
        ),
        pytest.param(
            ("--cache", "/path/to/cache", "--sysconfig", "/path/to/sysconfig.py"),
            "--cache requires --platform",
            id="sysconfig-and-cache",
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
    ("args", "already_exists", "create_kwargs"),
    [
        pytest.param(
            ["--platform", "android"],
            False,
            {
                "platform": "android",
                "with_pip": True,
            },
            id="platform",
        ),
        pytest.param(
            ["--platform", "android", "--without-pip"],
            False,
            {
                "platform": "android",
                "with_pip": False,
            },
            id="no-pip",
        ),
        pytest.param(
            ["--platform", "android", "--arch", "arm64_v8a"],
            False,
            {
                "platform": "android",
                "arch": "arm64_v8a",
            },
            id="platform-with-arch",
        ),
        pytest.param(
            ["--platform", "android", "--cache", "path/to/cache"],
            False,
            {
                "platform": "android",
                "cache_path": Path("path/to/cache"),
            },
            id="cache",
        ),
        pytest.param(
            ["--build-details", "path/to/build-config.json"],
            True,
            {"build_details_path": Path("path/to/build-config.json")},
            id="build-details",
        ),
        pytest.param(
            ["--sysconfig", "path/to/sysconfigdata.py"],
            False,
            {"sysconfigdata_path": Path("path/to/sysconfigdata.py")},
            id="sysconfig",
        ),
    ],
)
def test_valid_args(
    venv_path,
    mock_create_cross_venv,
    args,
    already_exists,
    create_kwargs,
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
        "with_pip": True,
    }
    kwargs.update(create_kwargs)
    mock_create_cross_venv.assert_called_once_with(venv_path, **kwargs)
