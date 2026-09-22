from unittest.mock import Mock

import pytest

from xvenv.__main__ import main


@pytest.fixture
def venv_path(tmp_path):
    return tmp_path / "x-venv"


@pytest.fixture
def mock_create(monkeypatch):
    create = Mock()
    monkeypatch.setattr("xvenv.__main__.venv.create", create)
    monkeypatch.setattr(
        "xvenv.__main__.convert_venv",
        Mock(return_value="test"),
    )
    return create


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
        ([], False, {"with_pip": True}),
        (["--without-pip"], False, {"with_pip": False}),
        ([], True, None),
    ],
)
def test_valid_args(venv_path, mock_create, args, already_exists, create_kwargs):
    """Verify some valid argument cases."""
    # If the venv should already exist, create it
    if already_exists:
        venv_path.mkdir()

    main(["--build-details", "path/to/build-config.json", *args, str(venv_path)])

    if create_kwargs is None:
        mock_create.assert_not_called()
    else:
        mock_create.assert_called_once_with(venv_path, **create_kwargs)
