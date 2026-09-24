import sys
from unittest.mock import Mock

import pytest

from xpython.platforms.ios import stage_and_run


@pytest.fixture
def mock_run(monkeypatch):
    mock = Mock()
    mock.return_value = Mock(returncode=0)
    monkeypatch.setattr("xpython.platforms.ios.subprocess.run", mock)
    return mock


@pytest.fixture
def testbed_layout(tmp_path):
    """Simulate the directory structure stage_and_run() expects to exist
    after cloning, without actually running the real testbed clone
    subprocess (which is mocked)."""
    archive_dir = tmp_path / "archive"
    (archive_dir / "testbed").mkdir(parents=True)
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    # Simulate the clone subcommand's effect by pre-creating the app/
    # and app_packages/ directories the real testbed clone would create.
    app_dir = work_dir / "testbed" / "iOSTestbed" / "app"
    app_packages_dir = work_dir / "testbed" / "iOSTestbed" / "app_packages"
    app_dir.mkdir(parents=True)
    app_packages_dir.mkdir(parents=True)

    return {
        "archive_dir": archive_dir,
        "work_dir": work_dir,
        "app_dir": app_dir,
        "app_packages_dir": app_packages_dir,
    }


def test_clones_testbed(mock_run, testbed_layout, tmp_path):
    """stage_and_run() clones the testbed before running."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[],
        packages_dir=packages_dir,
        module="pytest",
        module_args=["tests"],
        simulator=None,
        verbose=0,
    )

    clone_call = mock_run.call_args_list[0]
    args = clone_call.args[0]
    assert args[:2] == [sys.executable, str(testbed_layout["archive_dir"] / "testbed")]
    assert args[2] == "clone"
    assert args[3] == str(testbed_layout["work_dir"] / "testbed")


def test_copies_src_paths_into_app_dir(mock_run, testbed_layout, tmp_path):
    """Each --src path is copied into the cloned testbed's app/ directory."""
    src = tmp_path / "tests"
    src.mkdir()
    (src / "test_thing.py").write_text("def test_x(): pass\n")
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[src],
        packages_dir=packages_dir,
        module="pytest",
        module_args=[],
        simulator=None,
        verbose=0,
    )

    copied = testbed_layout["app_dir"] / "tests" / "test_thing.py"
    assert copied.is_file()
    assert copied.read_text() == "def test_x(): pass\n"


def test_copies_packages_into_app_packages_dir(mock_run, testbed_layout, tmp_path):
    """Contents of packages_dir are copied into app_packages/."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()
    (packages_dir / "requests").mkdir()
    (packages_dir / "requests" / "__init__.py").write_text("# fake requests\n")

    stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[],
        packages_dir=packages_dir,
        module="pytest",
        module_args=[],
        simulator=None,
        verbose=0,
    )

    copied = testbed_layout["app_packages_dir"] / "requests" / "__init__.py"
    assert copied.is_file()


def test_runs_with_module_and_args(mock_run, testbed_layout, tmp_path):
    """The run subcommand is invoked with -- <module> <module_args>."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[],
        packages_dir=packages_dir,
        module="pytest",
        module_args=["tests", "-v"],
        simulator=None,
        verbose=0,
    )

    run_call = mock_run.call_args_list[1]
    args = run_call.args[0]
    assert args[:2] == [sys.executable, str(testbed_layout["work_dir"] / "testbed")]
    assert args[2] == "run"
    assert args[-4:] == ["--", "pytest", "tests", "-v"]


def test_forwards_simulator_flag(mock_run, testbed_layout, tmp_path):
    """--simulator is forwarded to the run subcommand."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[],
        packages_dir=packages_dir,
        module="pytest",
        module_args=[],
        simulator="iPhone 16e",
        verbose=0,
    )

    run_call = mock_run.call_args_list[1]
    args = run_call.args[0]
    assert "--simulator" in args
    assert args[args.index("--simulator") + 1] == "iPhone 16e"


def test_forwards_verbose_flag(mock_run, testbed_layout, tmp_path):
    """verbose > 0 adds -v to the run subcommand."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[],
        packages_dir=packages_dir,
        module="pytest",
        module_args=[],
        simulator=None,
        verbose=1,
    )

    run_call = mock_run.call_args_list[1]
    args = run_call.args[0]
    assert "-v" in args


def test_returns_run_exit_code(mock_run, testbed_layout, tmp_path):
    """stage_and_run() returns the run subcommand's exit code verbatim."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()
    mock_run.side_effect = [
        Mock(returncode=0),  # clone
        Mock(returncode=3),  # run
    ]

    result = stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[],
        packages_dir=packages_dir,
        module="pytest",
        module_args=[],
        simulator=None,
        verbose=0,
    )

    assert result == 3


def test_omits_module_segment_when_module_is_none(mock_run, testbed_layout, tmp_path):
    """When module is None, the run subcommand's command has no trailing
    -- <module> <args> segment at all."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[],
        packages_dir=packages_dir,
        module=None,
        module_args=[],
        simulator=None,
        verbose=0,
    )

    run_call = mock_run.call_args_list[1]
    args = run_call.args[0]
    assert args == [sys.executable, str(testbed_layout["work_dir"] / "testbed"), "run"]
    assert "--" not in args


def test_omits_module_segment_but_keeps_simulator_and_verbose(
    mock_run, testbed_layout, tmp_path
):
    """module=None still allows --simulator/-v to be forwarded; only the
    trailing -- <module> <args> segment is omitted."""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    stage_and_run(
        archive_dir=testbed_layout["archive_dir"],
        work_dir=testbed_layout["work_dir"],
        src_paths=[],
        packages_dir=packages_dir,
        module=None,
        module_args=[],
        simulator="iPhone 16e",
        verbose=1,
    )

    run_call = mock_run.call_args_list[1]
    args = run_call.args[0]
    assert args == [
        sys.executable,
        str(testbed_layout["work_dir"] / "testbed"),
        "run",
        "--simulator",
        "iPhone 16e",
        "-v",
    ]
