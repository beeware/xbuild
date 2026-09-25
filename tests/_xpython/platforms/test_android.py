import sys
from unittest.mock import Mock

import pytest

from xpython.platforms.android import run, setup


@pytest.fixture
def mock_run(monkeypatch):
    mock = Mock()
    mock.return_value = Mock(returncode=0)
    monkeypatch.setattr("xpython.platforms.android.subprocess.run", mock)
    return mock


@pytest.fixture
def work_dir(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    return work


def test_testbed_clone(monkeypatch, tmp_path):
    """The testbed and each --src path is copied into work_dir/cwd."""
    # Monkeypatch so that it looks like we're
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    (archive_dir / "android.py").write_text("def main(): pass\n")
    (archive_dir / "testbed").mkdir(parents=True)
    (archive_dir / "testbed/build.gradle").write_text("# gradle stuff\n")

    for path in ["tests", "deep/other"]:
        src = tmp_path / path
        src.mkdir(parents=True)
        (src / "test_thing.py").write_text("def test_x(): pass\n")

    work_dir = tmp_path / "work"

    setup(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[
            tmp_path / "tests",
            tmp_path / "deep/other",
        ],
    )

    # Testbed was copied
    copied = work_dir / "android.py"
    assert copied.is_file()
    assert copied.read_text() == "def main(): pass\n"

    copied = work_dir / "testbed" / "build.gradle"
    assert copied.is_file()

    # The *leaf* folders have been preserved in the final location.
    for path in ["tests", "other"]:
        copied = work_dir / "src" / path / "test_thing.py"
        assert copied.is_file()
        assert copied.read_text() == "def test_x(): pass\n"


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS specific test")
def test_testbed_clone_macOS_ci(monkeypatch, tmp_path):
    """If running on GitHub Actions under macOS, an error is raised on clone."""
    # Monkeypatch so that it looks like we're in CI, regardless of whether we are.
    monkeypatch.setenv("GITHUB_ACTIONS", "1")

    with pytest.raises(
        RuntimeError,
        match=r"GitHub Actions can't start an Android emulator on a macOS runner.",
    ):
        setup(archive_dir=tmp_path / "archive", work_dir=tmp_path / "work")


def test_run_with_module_and_args(mock_run, work_dir):
    """The run subcommand is invoked with -- <module> <module_args>."""
    mock_run.return_value = Mock(returncode=3)

    result = run(
        work_dir=work_dir,
        args=["-m", "pytest", "tests", "-v"],
        managed=None,
        connected=None,
        verbose=0,
    )

    # Testbed was invoked
    args = mock_run.call_args.args[0]
    assert args[0] == str(work_dir / "android.py")
    assert args[1] == "test"
    assert "--site-packages" in args
    assert args[args.index("--site-packages") + 1] == str(work_dir / "site-packages")
    assert "--cwd" in args
    assert args[args.index("--cwd") + 1] == str(work_dir / "src")
    assert "--managed" in args
    assert args[args.index("--managed") + 1] == "maxVersion"
    assert "--connected" not in args
    assert args[-5:] == ["--", "-m", "pytest", "tests", "-v"]

    # Return code of the testbed is the result
    assert result == 3


def test_args_dash_c(mock_run, work_dir):
    """args starting with -c (not -m) are passed through
    verbatim, with no xpython-side validation or forced -m."""
    run(
        work_dir=work_dir,
        args=["-c", "print(1)"],
        managed=None,
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[-3:] == ["--", "-c", "print(1)"]


def test_args_empty(mock_run, work_dir):
    """An empty args list still results in a bare trailing --."""
    run(
        work_dir=work_dir,
        args=[],
        managed=None,
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[-1] == "--"


def test_forwards_managed_flag(mock_run, work_dir):
    """An explicit --managed overrides the default."""
    run(
        work_dir=work_dir,
        args=["-m", "pytest"],
        managed="minVersion",
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[args.index("--managed") + 1] == "minVersion"


def test_forwards_connected_flag(mock_run, work_dir):
    """--connected is forwarded instead of --managed when given."""
    run(
        work_dir=work_dir,
        args=["-m", "pytest"],
        managed=None,
        connected="emulator-5554",
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert "--managed" not in args
    assert "--connected" in args
    assert args[args.index("--connected") + 1] == "emulator-5554"


def test_forwards_verbose_flag(mock_run, work_dir):
    """verbose > 0 adds -v to the invocation."""
    run(
        work_dir=work_dir,
        args=["-m", "pytest"],
        managed=None,
        connected=None,
        verbose=1,
    )

    args = mock_run.call_args.args[0]
    assert "-v" in args
