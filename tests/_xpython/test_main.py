import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from xpython.__main__ import _parse_args, _run, main, main_parser
from xpython.project import (
    PROJECT_FILENAME,
    ProjectConfig,
    SetupOptions,
    read_project,
    write_project,
)
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
    config.packages_path.return_value = tmp_path / "site-packages"
    config.run_testbed.return_value = 0
    return config


@pytest.fixture
def mock_CrossVenvConfig(monkeypatch, mock_config):
    CrossVenvConfig = Mock(return_value=mock_config)
    CrossVenvConfig.from_current_env.return_value = mock_config
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
            "--simulator option also requires --platform ios",
            id="simulator-without-ios",
        ),
        pytest.param(
            ["--platform", "ios", "--managed", "maxVersion", "--", "-m", "pytest"],
            "--managed option also requires --platform android",
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
            "--connected option also requires --platform android",
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
    parser = main_parser()
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(parser, args)

    assert excinfo.value.code == 2
    assert error in capsys.readouterr().err


def test_defaults():
    """Default values are set correctly when only required args are given."""
    parser = main_parser()
    args = _parse_args(parser, ["--platform", "android"])

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
    assert args.project is None
    assert args.verbosity == 0
    assert args.forwarded_args == []
    assert args.use_current_env is False


def test_repeatable_flags():
    """-d/--dependency, --group, --find-links, --src can be repeated."""
    parser = main_parser()
    args = _parse_args(
        parser,
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
        ],
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
    parser = main_parser()
    args = _parse_args(parser, input_args)

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
    parser = main_parser()
    args = _parse_args(
        parser,
        ["--platform", "android", *archive_args, "--", "-m", "pytest"],
    )

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


@pytest.fixture
def cross_env(monkeypatch):
    """Simulate running inside an iOS cross env."""
    monkeypatch.setattr(sys, "cross_compiling", True, raising=False)
    monkeypatch.setattr(sys, "platform", "ios")


def test_no_config_outside_cross_env(monkeypatch, capsys):
    """Outside a cross env, a configuration source is required."""
    monkeypatch.delattr(sys, "cross_compiling", raising=False)

    parser = main_parser()
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(parser, ["--", "-m", "pytest"])

    assert excinfo.value.code == 2
    assert (
        "One of the arguments --build-details, --sysconfig, or --platform is required"
        in capsys.readouterr().err
    )


def test_no_config_in_cross_env(cross_env):
    """Inside a cross env, no configuration source is needed, and
    platform-specific options are validated against the current platform."""
    parser = main_parser()
    args = _parse_args(parser, ["--simulator", "iPhone 16e", "--", "-m", "pytest"])

    assert args.use_current_env is True
    assert args.platform is None
    assert args.simulator == "iPhone 16e"


def test_no_config_in_cross_env_wrong_platform_option(cross_env, capsys):
    """Inside an iOS cross env, Android-only options are rejected."""
    parser = main_parser()
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(parser, ["--managed", "maxVersion", "--", "-m", "pytest"])

    assert excinfo.value.code == 2
    assert (
        "--managed option also requires --platform android" in capsys.readouterr().err
    )


def test_explicit_config_in_cross_env(cross_env):
    """Inside a cross env, an explicit configuration source takes precedence."""
    parser = main_parser()
    args = _parse_args(parser, ["--platform", "android", "--managed", "maxVersion"])

    assert args.use_current_env is False
    assert args.platform == "android"


def test_run_current_env(
    cross_env,
    tmp_path,
    mock_CrossVenvConfig,
    mock_config,
    mock_resolve_requirements,
):
    """_run() uses the current env's config when no source is given."""
    parser = main_parser()
    args = _parse_args(parser, ["--", "-m", "pytest"])
    args.work_path = tmp_path / "work"
    args.work_path.mkdir()

    exit_code = _run(args)

    mock_CrossVenvConfig.assert_not_called()
    mock_CrossVenvConfig.from_current_env.assert_called_once_with()
    mock_config.create.assert_called_once_with(args.work_path / "venv", with_pip=True)
    assert exit_code == 0


def test_run_writes_project(
    tmp_path,
    monkeypatch,
    mock_CrossVenvConfig,
    mock_config,
    mock_resolve_requirements,
):
    """After a successful setup, the project file is written before the
    testbed is run."""
    monkeypatch.chdir(tmp_path)
    parser = main_parser()
    args = _parse_args(
        parser,
        [
            "--platform",
            "android",
            "-d",
            "pytest",
            "--src",
            "tests",
            "--",
            "-m",
            "pytest",
        ],
    )
    args.work_path = tmp_path / "work"
    args.work_path.mkdir()

    def check_project_written(**kwargs):
        assert (args.work_path / PROJECT_FILENAME).is_file()
        return 0

    mock_config.run_testbed.side_effect = check_project_written

    assert _run(args) == 0

    assert read_project(args.work_path) == ProjectConfig(
        platform="android",
        options=SetupOptions(
            dependencies=["pytest"],
            src=[tmp_path.resolve() / "tests"],
            platform="android",
        ),
    )


def test_run_install_failure_no_project(
    tmp_path,
    monkeypatch,
    mock_CrossVenvConfig,
    mock_config,
    mock_resolve_requirements,
):
    """If dependency installation fails, no project file is written."""
    mock_resolve_requirements.return_value = ["pytest"]
    monkeypatch.setattr(
        "xpython.__main__.install_requirements",
        Mock(side_effect=subprocess.CalledProcessError(1, ["pip"])),
    )
    parser = main_parser()
    args = _parse_args(parser, ["--platform", "android", "-d", "pytest"])
    args.work_path = tmp_path / "work"
    args.work_path.mkdir()

    with pytest.raises(subprocess.CalledProcessError):
        _run(args)

    assert not (args.work_path / PROJECT_FILENAME).exists()
    mock_config.run_testbed.assert_not_called()


@pytest.fixture
def native_env(monkeypatch):
    """Ensure we're not in a cross env."""
    monkeypatch.delattr(sys, "cross_compiling", raising=False)


@pytest.fixture
def reusable_work_path(tmp_path):
    """A work directory configured by a previous xpython run."""
    work_path = tmp_path / "work"
    work_path.mkdir()
    write_project(
        work_path,
        ProjectConfig(
            platform="android",
            options=SetupOptions(dependencies=["pytest"], platform="android"),
        ),
    )
    return work_path


@pytest.fixture
def mock_run_testbed(monkeypatch):
    run_testbed = Mock(return_value=3)
    monkeypatch.setattr("xpython.__main__.run_testbed", run_testbed)
    return run_testbed


def test_main_fresh_work_dir(
    native_env,
    tmp_path,
    mock_CrossVenvConfig,
    mock_config,
    mock_resolve_requirements,
):
    """A non-existent work dir is created and fully set up."""
    work_path = tmp_path / "work"

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--platform",
                "android",
                "--work-dir",
                str(work_path),
                "--",
                "-m",
                "pytest",
            ]
        )

    assert excinfo.value.code == 0
    mock_config.create.assert_called_once_with(
        work_path.resolve() / "venv", with_pip=True
    )
    mock_config.setup_testbed.assert_called_once()
    assert (work_path / PROJECT_FILENAME).is_file()


def test_main_reuse(
    native_env,
    reusable_work_path,
    mock_CrossVenvConfig,
    mock_config,
    mock_resolve_requirements,
    mock_run_testbed,
    capsys,
):
    """An existing, configured work dir is reused without any setup, and
    without requiring a platform."""
    install_requirements = Mock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("xpython.__main__.install_requirements", install_requirements)
        with pytest.raises(SystemExit) as excinfo:
            main(
                [
                    "--work-dir",
                    str(reusable_work_path),
                    "--connected",
                    "emulator-5554",
                    "--",
                    "-m",
                    "pytest",
                    "-k",
                    "widget",
                ]
            )

    assert excinfo.value.code == 3
    mock_CrossVenvConfig.assert_not_called()
    mock_CrossVenvConfig.from_current_env.assert_not_called()
    mock_resolve_requirements.assert_not_called()
    install_requirements.assert_not_called()
    mock_run_testbed.assert_called_once_with(
        "android",
        work_path=reusable_work_path.resolve(),
        args=["-m", "pytest", "-k", "widget"],
        simulator=None,
        managed=None,
        connected="emulator-5554",
        verbose=0,
    )
    assert "WARNING" not in capsys.readouterr().err


def test_main_reuse_in_cross_env(
    cross_env,
    reusable_work_path,
    mock_CrossVenvConfig,
    mock_run_testbed,
):
    """Inside a cross env, the recorded project wins over the current env."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--work-dir", str(reusable_work_path), "--managed", "maxVersion"])

    assert excinfo.value.code == 3
    mock_CrossVenvConfig.from_current_env.assert_not_called()
    assert mock_run_testbed.call_args.args == ("android",)


def test_main_reuse_warnings(
    native_env,
    reusable_work_path,
    mock_CrossVenvConfig,
    mock_run_testbed,
    capsys,
):
    """Setup options that differ from the recorded ones produce warnings and
    are ignored; matching options don't."""
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--platform",
                "android",
                "-d",
                "requests",
                "--group",
                "test",
                "--work-dir",
                str(reusable_work_path),
            ]
        )

    assert excinfo.value.code == 3
    err = capsys.readouterr().err
    assert "Ignoring --dependency [requests]" in err
    assert "configured with --dependency [pytest]" in err
    assert "Ignoring --group [test]" in err
    assert "Ignoring --platform" not in err
    mock_CrossVenvConfig.assert_not_called()
    assert mock_run_testbed.call_args.args == ("android",)


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(None, id="empty-dir"),
        pytest.param("not toml [", id="invalid-project"),
    ],
)
def test_main_existing_invalid_work_dir(
    native_env,
    tmp_path,
    content,
    mock_CrossVenvConfig,
    capsys,
):
    """An existing work dir without a valid project file is an error."""
    work_path = tmp_path / "work"
    work_path.mkdir()
    if content is not None:
        (work_path / PROJECT_FILENAME).write_text(content, encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "android", "--work-dir", str(work_path)])

    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "is not a valid xpython work directory" in err
    assert "choose a different --work-dir" in err
    mock_CrossVenvConfig.assert_not_called()


def test_parse_missing_config_new_work_dir(native_env, tmp_path, capsys):
    """Without a reusable work dir, a configuration source is still required."""
    parser = main_parser()
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(parser, ["--work-dir", str(tmp_path / "work")])

    assert excinfo.value.code == 2
    assert (
        "One of the arguments --build-details, --sysconfig, or --platform is required"
        in capsys.readouterr().err
    )


def test_parse_reuse(native_env, reusable_work_path, monkeypatch):
    """On reuse, the work dir is resolved and the project is loaded."""
    monkeypatch.chdir(reusable_work_path.parent)
    parser = main_parser()
    args = _parse_args(parser, ["--work-dir", "work"])

    assert args.work_path == reusable_work_path.resolve()
    assert args.project.platform == "android"


def test_parse_reuse_wrong_platform_option(native_env, reusable_work_path, capsys):
    """On reuse, device options are validated against the recorded platform."""
    parser = main_parser()
    with pytest.raises(SystemExit) as excinfo:
        _parse_args(
            parser,
            ["--work-dir", str(reusable_work_path), "--simulator", "iPhone 16e"],
        )

    assert excinfo.value.code == 2
    assert "--simulator option also requires --platform ios" in capsys.readouterr().err
