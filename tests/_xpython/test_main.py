import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from xpython.__main__ import _parse_args, main
from xvenv.api import CrossVenvResult


@pytest.mark.parametrize(
    ("args", "error"),
    [
        pytest.param(
            [
                "--platform",
                "android",
                "--simulator",
                "iPhone 16e",
                "--",
                "-m",
                "pytest",
            ],
            "--simulator requires --platform ios",
            id="simulator-without-ios",
        ),
        pytest.param(
            ["--platform", "ios", "--managed", "maxVersion", "--", "-m", "pytest"],
            "--managed requires --platform android",
            id="managed-without-android",
        ),
        pytest.param(
            [
                "--platform",
                "ios",
                "--connected",
                "emulator-5554",
                "--",
                "-m",
                "pytest",
            ],
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
                "--",
                "-m",
                "pytest",
            ],
            "not allowed with argument",
            id="managed-and-connected-together",
        ),
        pytest.param(
            ["--platform", "bogus", "--", "-m", "pytest"],
            "invalid choice",
            id="unknown-platform",
        ),
        pytest.param(
            ["--platform", "ios", "--", "pytest", "tests"],
            "-m",
            id="ios-forwarded-args-must-start-with-m",
        ),
        pytest.param(
            ["--platform", "ios", "--", "-m"],
            "-m",
            id="ios-forwarded-args-m-with-no-module-name",
        ),
    ],
)
def test_invalid_args(args, error, capsys):
    """Invalid flag combinations raise a usage error."""
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(args)

    assert excinfo.value.code == 2
    assert error in capsys.readouterr().err


def test_missing_platform(capsys):
    """--platform is required."""
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(["--", "-m", "pytest"])

    assert excinfo.value.code == 2
    assert "required" in capsys.readouterr().err


def test_defaults():
    """Default values are set correctly when only required args are given."""
    args = _parse_args(["--platform", "android"])

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
    assert args.forwarded_args == []


def test_repeatable_flags():
    """-d/--dependency, --group, --find-links, --src can be repeated."""
    args = _parse_args(
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
            "--",
            "-m",
            "pytest",
        ]
    )

    assert args.dependencies == ["requests", "attrs>=23"]
    assert args.groups == ["test", "extra"]
    assert args.find_links == ["/tmp/wheels"]
    assert args.src == [Path("tests"), Path("conftest.py")]
    assert args.module == "pytest"
    assert args.module_args == []


def test_ios_module_and_args_split():
    """iOS: -- -m MODULE arg1 arg2 splits into module + module_args, with
    the leading -m token stripped."""
    args = _parse_args(["--platform", "ios", "--", "-m", "pytest", "tests", "-v"])

    assert args.module == "pytest"
    assert args.module_args == ["tests", "-v"]


def test_ios_empty_forwarded_args_no_parse_error():
    """iOS: omitting -- (or providing an empty --) is not a parse-time
    error; module ends up None, module_args ends up empty."""
    args = _parse_args(["--platform", "ios"])

    assert args.module is None
    assert args.module_args == []


def test_ios_bare_trailing_separator_same_as_omitted():
    """iOS: an explicit trailing -- with nothing after it behaves the same
    as omitting -- entirely."""
    args = _parse_args(["--platform", "ios", "--"])

    assert args.module is None
    assert args.module_args == []


def test_ios_forwarded_args_with_embedded_double_dash():
    """Only the first -- is treated as the xpython/forwarded-args
    separator; a second -- embedded in the forwarded command is preserved
    verbatim in module_args."""
    args = _parse_args(["--platform", "ios", "--", "-m", "pytest", "--", "--some-flag"])

    assert args.module == "pytest"
    assert args.module_args == ["--", "--some-flag"]


def test_android_forwarded_args_accepts_dash_c():
    """Android: forwarded args starting with -c (not -m) are accepted with
    no xpython-side validation error, and stored verbatim."""
    args = _parse_args(["--platform", "android", "--", "-c", "print(1)"])

    assert args.forwarded_args == ["-c", "print(1)"]


def test_android_empty_forwarded_args_no_error():
    """Android: an empty forwarded-args list (bare trailing --, or --
    omitted entirely) is not a parse-time error."""
    args = _parse_args(["--platform", "android"])

    assert args.forwarded_args == []


def test_android_forwarded_args_with_embedded_double_dash():
    """Android: only the first -- is the separator; embedded -- in the
    forwarded command is preserved verbatim."""
    args = _parse_args(
        ["--platform", "android", "--", "-m", "pytest", "--", "--some-flag"]
    )

    assert args.forwarded_args == ["-m", "pytest", "--", "--some-flag"]


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
