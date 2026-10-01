from pathlib import Path
from unittest.mock import Mock

import pytest

from xpython.__main__ import _parse_args, _run
from xvenv.convert import CrossVenvConfig


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(
        spec=CrossVenvConfig,
        platform="android",
        arch="arm64",
        archive_path=None,
        build_details_path=None,
        sysconfigdata_path=None,
    )
    config = Mock()
    config.packages_path.return_value = tmp_path / "site-packages"
    config.run_testbed.return_value = 0
    return config


@pytest.fixture
def mock_CrossVenvConfig(monkeypatch, mock_config):
    CrossVenvConfig = Mock(return_value=mock_config)
    monkeypatch.setattr("xpython.__main__.CrossVenvConfig", CrossVenvConfig)
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
            "--arch requires --platform",
            id="sysconfig-and-arch",
        ),
        pytest.param(
            ("--cache", "/path/to/cache", "--sysconfig", "/path/to/sysconfig.py"),
            "--cache requires --platform",
            id="sysconfig-and-cache",
        ),
        pytest.param(
            ("--cache", "/path/to/cache", "--archive", "/path/to/archive"),
            "not allowed with argument",
            id="cache-and-archive",
        ),
        pytest.param(
            ("--archive", "/path/to/archive", "--sysconfig", "/path/to/sysconfig.py"),
            "--archive requires --platform",
            id="sysconfig-and-archive",
        ),
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
            ["--", "-m", "pytest"],
            "required",
            id="missing-platform",
        ),
    ],
)
def test_invalid_args(args, error, capsys):
    """Invalid flag combinations raise a usage error."""
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(args)

    assert excinfo.value.code == 2
    assert error in capsys.readouterr().err


def test_defaults():
    """Default values are set correctly when only required args are given."""
    args = _parse_args(["--platform", "android"])

    assert args.platform == "android"
    assert args.arch is None
    assert args.cache is None
    assert args.archive is None
    assert args.dependencies == []
    assert args.groups == []
    assert args.find_links == []
    assert args.src == []
    assert args.simulator is None
    assert args.managed is None
    assert args.connected is None
    assert args.work_path is None
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
    assert args.forwarded_args == ["-m", "pytest"]


@pytest.mark.parametrize(
    ("input_args", "forwarded_args"),
    [
        pytest.param(
            ["--platform", "android", "--", "-m", "pytest", "module"],
            ["-m", "pytest", "module"],
            id="module",
        ),
        pytest.param(
            ["--platform", "android", "--", "-m", "pytest", "module", "--", "--other"],
            ["-m", "pytest", "module", "--", "--other"],
            id="module-with-extra",
        ),
        pytest.param(
            ["--platform", "android", "--", "-c", "print(1)"],
            ["-c", "print(1)"],
            id="inline",
        ),
        pytest.param(
            ["--platform", "android", "--", "foobar.py", "--arg"],
            ["foobar.py", "--arg"],
            id="script",
        ),
        pytest.param(
            ["--platform", "android"],
            [],
            id="empty",
        ),
        pytest.param(
            ["--platform", "android", "--"],
            [],
            id="explicit-empty",
        ),
    ],
)
def test_forwarded_args(input_args, forwarded_args):
    """Android: forwarded args starting with -c (not -m) are accepted with
    no xpython-side validation error, and stored verbatim."""
    args = _parse_args(input_args)

    assert args.forwarded_args == forwarded_args


@pytest.fixture
def mock_resolve_requirements(monkeypatch):
    resolve_requirements = Mock(return_value=[])
    monkeypatch.setattr("xpython.__main__.resolve_requirements", resolve_requirements)
    return resolve_requirements


@pytest.mark.parametrize(
    ("archive_args", "expected_archive_path"),
    [
        pytest.param(
            ["--archive", "path/to/archive"],
            Path("path/to/archive"),
            id="with-archive",
        ),
        pytest.param(
            [],
            None,
            id="without-archive",
        ),
    ],
)
def test_run(
    archive_args,
    expected_archive_path,
    tmp_path,
    mock_CrossVenvConfig,
    mock_config,
    mock_resolve_requirements,
):
    """Environment config arguments are passed to run."""
    args = _parse_args(["--platform", "android", *archive_args, "--", "-m", "pytest"])
    args.work_path = tmp_path / "work"
    args.work_path.mkdir()

    exit_code = _run(args)

    mock_CrossVenvConfig.assert_called_once_with(
        platform="android",
        arch=None,
        archive_path=expected_archive_path,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )
    mock_config.create.assert_called_once_with(args.work_path / "venv", with_pip=True)
    mock_config.setup_testbed.assert_called_once_with(
        work_path=args.work_path,
        src_paths=[],
    )
    mock_config.run_testbed.assert_called_once_with(
        work_path=args.work_path,
        args=["-m", "pytest"],
        simulator=None,
        managed=None,
        connected=None,
        verbose=0,
    )
    assert exit_code == 0
