import sys
from unittest.mock import Mock

import pytest

from xpython.platforms.ios import run, setup


@pytest.fixture
def mock_run(monkeypatch):
    mock = Mock()
    mock.return_value = Mock(returncode=0)
    monkeypatch.setattr("xpython.platforms.ios.subprocess.run", mock)
    return mock


@pytest.fixture
def testbed_layout(tmp_path):
    """Simulate the directory structure run() expects to exist
    after setup(), without actually running the real testbed clone
    subprocess."""
    work_path = tmp_path / "work"
    work_path.mkdir()

    # Simulate the clone subcommand's effect by pre-creating the app/
    # and app_packages/ directories the real testbed clone would create.
    app_path = work_path / "testbed" / "iOSTestbed" / "app"
    app_packages_path = work_path / "testbed" / "iOSTestbed" / "app_packages"
    app_path.mkdir(parents=True)
    app_packages_path.mkdir(parents=True)

    return {
        "work_path": work_path,
        "app_path": app_path,
        "app_packages_path": app_packages_path,
    }


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_testbed_clone_macOS(mock_run, tmp_path):
    """The tesbed and each --src path is copied into the cloned testbed's app/
    directory."""
    archive_path = tmp_path / "archive"
    (archive_path / "testbed").mkdir(parents=True)

    work_path = tmp_path / "work"
    work_path.mkdir()
    app_path = work_path / "testbed" / "iOSTestbed" / "app"

    for path in ["tests", "deep/other"]:
        src = tmp_path / path
        src.mkdir(parents=True)
        (src / "test_thing.py").write_text("def test_x(): pass\n")

    setup(
        archive_path=archive_path,
        work_path=work_path,
        src_paths=[
            tmp_path / "tests",
            tmp_path / "deep/other",
        ],
    )

    # Clone was invoked
    clone_call = mock_run.call_args_list[0]
    args = clone_call.args[0]
    assert args[:2] == [sys.executable, str(archive_path / "testbed")]
    assert args[2] == "clone"
    assert args[3] == str(work_path / "testbed")

    # The *leaf* folders have been preserved in the final location.
    for path in ["tests", "other"]:
        copied = app_path / path / "test_thing.py"
        assert copied.is_file()
        assert copied.read_text() == "def test_x(): pass\n"


@pytest.mark.skipif(sys.platform == "darwin", reason="non-macOS-specific test")
def test_testbed_clone_non_macOS(tmp_path):
    """Testbed cloning fails on non-macOS platforms."""

    with pytest.raises(
        RuntimeError,
        match=r"Can't run an iOS project on non-macOS hardware.",
    ):
        setup(
            archive_path=tmp_path / "archive",
            work_path=tmp_path / "work",
            src_paths=[],
        )


def test_run_with_module_and_args(mock_run, testbed_layout):
    """The run subcommand is invoked with -- <module> <module_args>."""
    mock_run.return_value = Mock(returncode=3)

    result = run(
        work_path=testbed_layout["work_path"],
        args=["-m", "pytest", "tests", "-v"],
        simulator=None,
        verbose=0,
    )

    # Testbed was invoked
    mock_run.assert_called_once_with(
        [
            sys.executable,
            str(testbed_layout["work_path"] / "testbed"),
            "run",
            "--",
            "pytest",
            "tests",
            "-v",
        ],
        check=False,
    )

    # Return code of the testbed is the result
    assert result == 3


def test_args_empty(mock_run, testbed_layout):
    """An empty args list still results in a bare trailing --."""
    run(
        work_path=testbed_layout["work_path"],
        args=[],
        simulator=None,
        verbose=0,
    )

    mock_run.assert_called_once_with(
        [
            sys.executable,
            str(testbed_layout["work_path"] / "testbed"),
            "run",
            "--",
        ],
        check=False,
    )


def test_forwards_simulator_flag(mock_run, testbed_layout):
    """--simulator is forwarded to the run subcommand."""
    run(
        work_path=testbed_layout["work_path"],
        args=["-m", "pytest"],
        simulator="iPhone 16e",
        verbose=0,
    )

    mock_run.assert_called_once_with(
        [
            sys.executable,
            str(testbed_layout["work_path"] / "testbed"),
            "run",
            "--simulator",
            "iPhone 16e",
            "--",
            "pytest",
        ],
        check=False,
    )


def test_forwards_verbose_flag(mock_run, testbed_layout, tmp_path):
    """verbose > 0 adds -v to the run subcommand."""
    run(
        work_path=testbed_layout["work_path"],
        args=["-m", "pytest"],
        simulator=None,
        verbose=1,
    )

    mock_run.assert_called_once_with(
        [
            sys.executable,
            str(testbed_layout["work_path"] / "testbed"),
            "run",
            "-v",
            "--",
            "pytest",
        ],
        check=False,
    )


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["-m"], id="missing-module"),
        pytest.param(["-c", "print('hello')"], id="inline"),
        pytest.param(["hello.py"], id="script"),
    ],
)
def test_bad_args(mock_run, testbed_layout, args):
    """Unsupported arguments to run() raise a ValueError."""

    with pytest.raises(
        ValueError, match="iOS requires -m <module> as the first two arguments after --"
    ):
        run(
            work_path=testbed_layout["work_path"],
            args=args,
            simulator=None,
            verbose=0,
        )

    # Run wasn't called.
    mock_run.assert_not_called()
