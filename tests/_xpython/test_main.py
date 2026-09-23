from pathlib import Path

import pytest

from xpython.__main__ import main, main_parser


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
