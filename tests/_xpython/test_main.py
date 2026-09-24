from pathlib import Path

import pytest

from xpython.__main__ import _parse_args


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
