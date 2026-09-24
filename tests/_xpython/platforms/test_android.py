from unittest.mock import Mock

import pytest

from xpython.platforms.android import stage_and_run


@pytest.fixture
def mock_run(monkeypatch):
    mock = Mock()
    mock.return_value = Mock(returncode=0)
    monkeypatch.setattr("xpython.platforms.android.subprocess.run", mock)
    return mock


@pytest.fixture
def archive_dir(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "android.py").write_text("# fake driver\n")
    return archive


@pytest.fixture
def work_dir(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    return work


@pytest.fixture
def packages_dir(tmp_path):
    packages = tmp_path / "packages"
    packages.mkdir()
    return packages


def test_builds_site_packages_from_packages_dir(
    mock_run, archive_dir, work_dir, packages_dir
):
    """Contents of packages_dir are copied into work_dir/site-packages."""
    (packages_dir / "requests").mkdir()
    (packages_dir / "requests" / "__init__.py").write_text("# fake requests\n")

    stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[],
        packages_dir=packages_dir,
        forwarded_args=["-m", "pytest"],
        managed=None,
        connected=None,
        verbose=0,
    )

    copied = work_dir / "site-packages" / "requests" / "__init__.py"
    assert copied.is_file()


def test_builds_cwd_from_src_paths(mock_run, archive_dir, work_dir, packages_dir):
    """Each --src path is copied into work_dir/cwd."""
    src = work_dir.parent / "tests"
    src.mkdir()
    (src / "test_thing.py").write_text("def test_x(): pass\n")

    stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[src],
        packages_dir=packages_dir,
        forwarded_args=["-m", "pytest"],
        managed=None,
        connected=None,
        verbose=0,
    )

    copied = work_dir / "cwd" / "tests" / "test_thing.py"
    assert copied.is_file()


def test_invokes_android_py_test_with_defaults(
    mock_run, archive_dir, work_dir, packages_dir
):
    """android.py test is invoked with --site-packages, --cwd, and default
    --managed maxVersion when neither --managed nor --connected is given;
    forwarded_args is passed through verbatim after --."""
    stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[],
        packages_dir=packages_dir,
        forwarded_args=["-m", "pytest", "tests"],
        managed=None,
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[0] == str(archive_dir / "android.py")
    assert args[1] == "test"
    assert "--site-packages" in args
    assert args[args.index("--site-packages") + 1] == str(work_dir / "site-packages")
    assert "--cwd" in args
    assert args[args.index("--cwd") + 1] == str(work_dir / "cwd")
    assert "--managed" in args
    assert args[args.index("--managed") + 1] == "maxVersion"
    assert "--connected" not in args
    assert args[-4:] == ["--", "-m", "pytest", "tests"]


def test_forwards_arbitrary_args_including_dash_c(
    mock_run, archive_dir, work_dir, packages_dir
):
    """forwarded_args starting with -c (not -m) are passed through
    verbatim, with no xpython-side validation or forced -m."""
    stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[],
        packages_dir=packages_dir,
        forwarded_args=["-c", "print(1)"],
        managed=None,
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[-3:] == ["--", "-c", "print(1)"]


def test_forwards_empty_args_as_bare_double_dash(
    mock_run, archive_dir, work_dir, packages_dir
):
    """An empty forwarded_args list still results in a bare trailing --
    (no error, no forced -m); android.py's own driver defaults to -m test
    in this case."""
    stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[],
        packages_dir=packages_dir,
        forwarded_args=[],
        managed=None,
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[-1] == "--"


def test_forwards_managed_flag(mock_run, archive_dir, work_dir, packages_dir):
    """An explicit --managed overrides the default."""
    stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[],
        packages_dir=packages_dir,
        forwarded_args=["-m", "pytest"],
        managed="minVersion",
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[args.index("--managed") + 1] == "minVersion"


def test_forwards_connected_flag(mock_run, archive_dir, work_dir, packages_dir):
    """--connected is forwarded instead of --managed when given."""
    stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[],
        packages_dir=packages_dir,
        forwarded_args=["-m", "pytest"],
        managed=None,
        connected="emulator-5554",
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert "--managed" not in args
    assert "--connected" in args
    assert args[args.index("--connected") + 1] == "emulator-5554"


def test_forwards_verbose_flag(mock_run, archive_dir, work_dir, packages_dir):
    """verbose > 0 adds -v to the invocation."""
    stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[],
        packages_dir=packages_dir,
        forwarded_args=["-m", "pytest"],
        managed=None,
        connected=None,
        verbose=1,
    )

    args = mock_run.call_args.args[0]
    assert "-v" in args


def test_returns_exit_code(mock_run, archive_dir, work_dir, packages_dir):
    """stage_and_run() returns the driver's exit code verbatim."""
    mock_run.return_value = Mock(returncode=7)

    result = stage_and_run(
        archive_dir=archive_dir,
        work_dir=work_dir,
        src_paths=[],
        packages_dir=packages_dir,
        forwarded_args=["-m", "pytest"],
        managed=None,
        connected=None,
        verbose=0,
    )

    assert result == 7
