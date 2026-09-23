import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from xpython.__main__ import main, main_parser
from xvenv.api import CrossVenvResult


@pytest.mark.parametrize(
    ("args", "error"),
    [
        pytest.param(
            ["--platform", "android", "--simulator", "iPhone 16e", "-m", "pytest"],
            "--simulator requires --platform ios",
            id="simulator-without-ios",
        ),
        pytest.param(
            ["--platform", "ios", "--managed", "maxVersion", "-m", "pytest"],
            "--managed requires --platform android",
            id="managed-without-android",
        ),
        pytest.param(
            ["--platform", "ios", "--connected", "emulator-5554", "-m", "pytest"],
            "--connected requires --platform android",
            id="connected-without-android",
        ),
        pytest.param(
            [
                "--platform",
                "android",
                "--managed",
                "maxVersion",
                "--connected",
                "emulator-5554",
                "-m",
                "pytest",
            ],
            "not allowed with argument",
            id="managed-and-connected-together",
        ),
        pytest.param(
            ["--platform", "bogus", "-m", "pytest"],
            "invalid choice",
            id="unknown-platform",
        ),
    ],
)
def test_invalid_args(args, error, capsys):
    """Invalid flag combinations raise a usage error."""
    with pytest.raises(SystemExit) as excinfo:
        main(args)

    assert excinfo.value.code == 2
    assert error in capsys.readouterr().err


def test_missing_platform(capsys):
    """--platform is required."""
    with pytest.raises(SystemExit) as excinfo:
        main(["-m", "pytest"])

    assert excinfo.value.code == 2
    assert "required" in capsys.readouterr().err


def test_missing_module_args(capsys):
    """`-m` with no module name is a usage error."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "android", "-m"])

    assert excinfo.value.code == 2
    assert "the following arguments are required: -m" in capsys.readouterr().err


def test_missing_m_flag(capsys):
    """Omitting -m entirely is a usage error."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "android"])

    assert excinfo.value.code == 2
    assert "the following arguments are required: -m" in capsys.readouterr().err


def test_module_and_args_split():
    """-m MODULE arg1 arg2 splits into module + module_args."""
    parser = main_parser()

    args = parser.parse_args(["--platform", "ios", "-m", "pytest", "tests", "-v"])

    assert args.module_and_args == ["pytest", "tests", "-v"]


def test_defaults():
    """Default values are set correctly when only required args are given."""
    parser = main_parser()

    args = parser.parse_args(["--platform", "android", "-m", "pytest"])

    assert args.platform == "android"
    assert args.arch is None
    assert args.cache is None
    assert args.dependencies == []
    assert args.groups == []
    assert args.find_links == []
    assert args.src == []
    assert args.simulator is None
    assert args.managed is None
    assert args.connected is None
    assert args.work_dir is None
    assert args.verbosity == 0


def test_repeatable_flags():
    """-d/--dependency, --group, --find-links, --src can be repeated."""
    parser = main_parser()

    args = parser.parse_args(
        [
            "--platform",
            "ios",
            "-d",
            "requests",
            "-d",
            "attrs>=23",
            "--group",
            "test",
            "--group",
            "extra",
            "--find-links",
            "/tmp/wheels",
            "--src",
            "tests",
            "--src",
            "conftest.py",
            "-m",
            "pytest",
        ]
    )

    assert args.dependencies == ["requests", "attrs>=23"]
    assert args.groups == ["test", "extra"]
    assert args.find_links == ["/tmp/wheels"]
    assert args.src == [Path("tests"), Path("conftest.py")]


@pytest.fixture
def mock_pipeline(monkeypatch, tmp_path):
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    mocks = {
        "create_cross_venv": Mock(
            return_value=CrossVenvResult(
                description="ios arm64-iphonesimulator",
                archive_dir=archive_dir,
            )
        ),
        "resolve_requirements": Mock(return_value=["requests"]),
        "install_requirements": Mock(),
        "ios_stage_and_run": Mock(return_value=0),
        "android_stage_and_run": Mock(return_value=0),
    }
    monkeypatch.setattr(
        "xpython.__main__.create_cross_venv", mocks["create_cross_venv"]
    )
    monkeypatch.setattr(
        "xpython.__main__.resolve_requirements", mocks["resolve_requirements"]
    )
    monkeypatch.setattr(
        "xpython.__main__.install_requirements", mocks["install_requirements"]
    )
    monkeypatch.setattr(
        "xpython.__main__.ios_stage_and_run", mocks["ios_stage_and_run"]
    )
    monkeypatch.setattr(
        "xpython.__main__.android_stage_and_run", mocks["android_stage_and_run"]
    )
    return mocks


def test_main_ios_end_to_end_with_temp_dir(mock_pipeline):
    """main() creates a cross-venv, installs deps, and dispatches to the
    iOS platform module, using a temp dir that gets cleaned up."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "ios", "-d", "requests", "-m", "pytest", "tests"])

    assert excinfo.value.code == 0
    mock_pipeline["create_cross_venv"].assert_called_once()
    create_call_args = mock_pipeline["create_cross_venv"].call_args
    assert create_call_args.args[1] == "ios"

    mock_pipeline["resolve_requirements"].assert_called_once_with(
        ["requests"], [], Path("pyproject.toml")
    )
    mock_pipeline["install_requirements"].assert_called_once()
    mock_pipeline["ios_stage_and_run"].assert_called_once()
    stage_kwargs = mock_pipeline["ios_stage_and_run"].call_args.kwargs
    assert stage_kwargs["module"] == "pytest"
    assert stage_kwargs["module_args"] == ["tests"]
    mock_pipeline["android_stage_and_run"].assert_not_called()

    # The temp dir passed to create_cross_venv should no longer exist
    # after main() returns (it's cleaned up).
    venv_path_used = create_call_args.args[0]
    assert not venv_path_used.parent.exists()


def test_main_android_dispatches_to_android_module(mock_pipeline):
    """--platform android dispatches to android_stage_and_run, not iOS."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "android", "-m", "pytest"])

    assert excinfo.value.code == 0
    mock_pipeline["android_stage_and_run"].assert_called_once()
    mock_pipeline["ios_stage_and_run"].assert_not_called()
    stage_kwargs = mock_pipeline["android_stage_and_run"].call_args.kwargs
    assert stage_kwargs["managed"] is None
    assert stage_kwargs["connected"] is None


def test_main_propagates_nonzero_exit_code(mock_pipeline):
    """A nonzero exit code from the platform module propagates verbatim."""
    mock_pipeline["ios_stage_and_run"].return_value = 3

    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "ios", "-m", "pytest"])

    assert excinfo.value.code == 3


def test_main_work_dir_used_and_not_cleaned_up(mock_pipeline, tmp_path):
    """--work-dir DIR is used instead of a temp dir, and is not deleted."""
    work_dir = tmp_path / "my-work-dir"

    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "ios", "--work-dir", str(work_dir), "-m", "pytest"])

    assert excinfo.value.code == 0
    assert work_dir.exists()
    create_call_args = mock_pipeline["create_cross_venv"].call_args
    assert create_call_args.args[0] == work_dir / "venv"


def test_main_skips_install_when_no_requirements(mock_pipeline):
    """install_requirements() is not called if resolve_requirements()
    returns an empty list."""
    mock_pipeline["resolve_requirements"].return_value = []

    with pytest.raises(SystemExit):
        main(["--platform", "ios", "-m", "pytest"])

    mock_pipeline["install_requirements"].assert_not_called()


def test_main_reports_dependency_resolution_error(mock_pipeline, capsys):
    """A ValueError from resolve_requirements() is reported via _error()
    and exits with code 1."""
    mock_pipeline["resolve_requirements"].side_effect = ValueError(
        "Dependency group 'missing' not found"
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "ios", "--group", "missing", "-m", "pytest"])

    assert excinfo.value.code == 1
    assert "missing" in capsys.readouterr().err


def test_main_reports_create_cross_venv_error(mock_pipeline, capsys):
    """A ValueError from create_cross_venv() is reported via _error() and
    exits with code 1."""
    mock_pipeline["create_cross_venv"].side_effect = ValueError("bad arch")

    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "ios", "--arch", "bogus", "-m", "pytest"])

    assert excinfo.value.code == 1
    assert "bad arch" in capsys.readouterr().err


def test_main_reports_pip_install_error(mock_pipeline, capsys):
    """A CalledProcessError from install_requirements() is reported via
    _error() and exits with code 1, not an unhandled traceback."""
    mock_pipeline["install_requirements"].side_effect = subprocess.CalledProcessError(
        1, ["pip", "install"]
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "ios", "-d", "requests", "-m", "pytest"])

    assert excinfo.value.code == 1
    assert "testbed" in capsys.readouterr().err.lower()
