import re
import tomllib
from argparse import Namespace
from pathlib import Path

import pytest

import xpython
from xpython.project import (
    PROJECT_FILENAME,
    InvalidProjectError,
    ProjectConfig,
    SetupOptions,
    option_discrepancies,
    read_project,
    write_project,
)


def make_args(**overrides):
    values = {
        "dependencies": [],
        "groups": [],
        "find_links": [],
        "src": [],
        "platform": None,
        "arch": None,
        "cache": None,
        "archive": None,
        "build_details_path": None,
        "sysconfigdata_path": None,
    }
    values.update(overrides)
    return Namespace(**values)


def test_from_args_defaults():
    """No setup options given produces empty options."""
    assert SetupOptions.from_args(make_args()) == SetupOptions()


def test_from_args_resolves_paths(tmp_path, monkeypatch):
    """Paths are resolved to absolute paths; find-links URLs are kept as-is."""
    monkeypatch.chdir(tmp_path)
    resolved = tmp_path.resolve()

    options = SetupOptions.from_args(
        make_args(
            dependencies=["pytest"],
            groups=["test"],
            find_links=["wheels", "https://example.com/simple"],
            src=[Path("tests")],
            platform="android",
            arch="aarch64",
            cache=Path("cache"),
            archive=Path("archive"),
            build_details_path=Path("build-details.json"),
            sysconfigdata_path=Path("_sysconfigdata.py"),
        )
    )

    assert options == SetupOptions(
        dependencies=["pytest"],
        groups=["test"],
        find_links=[str(resolved / "wheels"), "https://example.com/simple"],
        src=[resolved / "tests"],
        platform="android",
        arch="aarch64",
        cache=resolved / "cache",
        archive=resolved / "archive",
        build_details=resolved / "build-details.json",
        sysconfig=resolved / "_sysconfigdata.py",
    )


def test_round_trip(tmp_path):
    """A written project can be read back unchanged."""
    options = SetupOptions(
        dependencies=["pytest", "attrs>=23"],
        groups=["test"],
        find_links=["/wheels", "https://example.com/simple"],
        src=[Path("/src/tests")],
        platform="ios",
        arch="arm64-iphonesimulator",
        cache=Path("/cache"),
        archive=Path("/archive"),
        build_details=Path("/build-details.json"),
        sysconfig=Path("/_sysconfigdata.py"),
    )
    config = ProjectConfig(platform="ios", options=options)

    write_project(tmp_path, config)

    assert read_project(tmp_path) == config


def test_written_format(tmp_path):
    """The file records the schema and version; unset scalars are omitted and
    lists are always written."""
    write_project(tmp_path, ProjectConfig(platform="android", options=SetupOptions()))

    with (tmp_path / PROJECT_FILENAME).open("rb") as f:
        data = tomllib.load(f)

    assert data == {
        "schema": 1,
        "xpython-version": xpython.__version__,
        "platform": "android",
        "options": {
            "dependencies": [],
            "groups": [],
            "find-links": [],
            "src": [],
        },
    }
    assert read_project(tmp_path) == ProjectConfig(
        platform="android", options=SetupOptions()
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        pytest.param(None, "xpython.toml not found", id="missing"),
        pytest.param("not toml [", "xpython.toml could not be parsed", id="bad-toml"),
        pytest.param(
            'schema = 2\nplatform = "android"\n[options]\n',
            "unsupported xpython.toml schema 2",
            id="future-schema",
        ),
        pytest.param(
            'schema = true\nplatform = "android"\n[options]\n',
            "unsupported xpython.toml schema True",
            id="bool-schema",
        ),
        pytest.param(
            'platform = "android"\n[options]\n',
            "unsupported xpython.toml schema None",
            id="no-schema",
        ),
        pytest.param(
            'schema = 1\nplatform = "bogus"\n[options]\n',
            "unknown platform 'bogus'",
            id="bad-platform",
        ),
        pytest.param(
            'schema = 1\nplatform = "android"\n',
            "missing [options] table",
            id="no-options",
        ),
        pytest.param(
            'schema = 1\nplatform = "android"\n[options]\ndependencies = "pytest"\n',
            "option 'dependencies' must be a list of strings",
            id="bad-list",
        ),
        pytest.param(
            'schema = 1\nplatform = "android"\n[options]\narch = 3\n',
            "option 'arch' must be a string",
            id="bad-scalar",
        ),
    ],
)
def test_read_invalid(tmp_path, content, message):
    """Invalid or missing project files raise InvalidProjectError."""
    if content is not None:
        (tmp_path / PROJECT_FILENAME).write_text(content, encoding="utf-8")

    with pytest.raises(InvalidProjectError, match=re.escape(message)):
        read_project(tmp_path)


RECORDED = SetupOptions(
    dependencies=["pytest"],
    src=[Path("/abs/tests")],
    platform="android",
    cache=Path("/abs/cache"),
)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        pytest.param(SetupOptions(), [], id="nothing-given"),
        pytest.param(
            SetupOptions(
                dependencies=["pytest"],
                src=[Path("/abs/tests")],
                platform="android",
                cache=Path("/abs/cache"),
            ),
            [],
            id="all-match",
        ),
        pytest.param(
            SetupOptions(dependencies=["requests"]),
            [("--dependency", "[pytest]", "[requests]")],
            id="list-differs",
        ),
        pytest.param(
            SetupOptions(groups=["test"]),
            [("--group", "[]", "[test]")],
            id="list-not-recorded",
        ),
        pytest.param(
            SetupOptions(arch="x86_64"),
            [("--arch", "(not set)", "x86_64")],
            id="scalar-not-recorded",
        ),
        pytest.param(
            SetupOptions(cache=Path("/other")),
            [("--cache", "/abs/cache", "/other")],
            id="path-differs",
        ),
        pytest.param(
            SetupOptions(platform="ios", src=[Path("/abs/other")]),
            [
                ("--src", "[/abs/tests]", "[/abs/other]"),
                ("--platform", "android", "ios"),
            ],
            id="multiple",
        ),
    ],
)
def test_option_discrepancies(given, expected):
    """Only explicitly given options that differ are reported, in field order."""
    assert option_discrepancies(RECORDED, given) == expected
