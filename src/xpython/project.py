"""Recording and reading the configuration of an xpython work directory."""

from __future__ import annotations

import argparse
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

import xpython

PROJECT_FILENAME = "xpython.toml"
SCHEMA_VERSION = 1
PLATFORMS = ("ios", "android", "emscripten")

# (SetupOptions attribute, TOML key, CLI flag, kind)
# kind is one of "list" (list[str]), "path-list" (list[Path]),
# "str" (str | None) or "path" (Path | None).
_OPTIONS = (
    ("dependencies", "dependencies", "--dependency", "list"),
    ("groups", "groups", "--group", "list"),
    ("find_links", "find-links", "--find-links", "list"),
    ("src", "src", "--src", "path-list"),
    ("platform", "platform", "--platform", "str"),
    ("arch", "arch", "--arch", "str"),
    ("cache", "cache", "--cache", "path"),
    ("archive", "archive", "--archive", "path"),
    ("build_details", "build-details", "--build-details", "path"),
    ("sysconfig", "sysconfig", "--sysconfig", "path"),
)


class InvalidProjectError(ValueError):
    """The work directory does not contain a valid xpython project file."""


def _resolve(path: Path | None) -> Path | None:
    return None if path is None else Path(path).resolve()


def _resolve_link(link: str) -> str:
    # pip's --find-links accepts URLs as well as local paths.
    return link if "://" in link else str(Path(link).resolve())


@dataclass
class SetupOptions:
    """The options used to set up an xpython work directory."""

    dependencies: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    find_links: list[str] = field(default_factory=list)
    src: list[Path] = field(default_factory=list)
    platform: str | None = None
    arch: str | None = None
    cache: Path | None = None
    archive: Path | None = None
    build_details: Path | None = None
    sysconfig: Path | None = None

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> SetupOptions:
        """Extract the setup options from parsed CLI arguments, resolving
        any paths to absolute paths.

        :param args: The parsed xpython CLI namespace.
        :returns: The normalized setup options.
        """
        return cls(
            dependencies=list(args.dependencies),
            groups=list(args.groups),
            find_links=[_resolve_link(link) for link in args.find_links],
            src=[Path(path).resolve() for path in args.src],
            platform=args.platform,
            arch=args.arch,
            cache=_resolve(args.cache),
            archive=_resolve(args.archive),
            build_details=_resolve(args.build_details_path),
            sysconfig=_resolve(args.sysconfigdata_path),
        )

    def to_toml(self) -> dict[str, Any]:
        """Convert to a TOML-serializable table. Unset scalars are omitted."""
        data: dict[str, Any] = {}
        for attr, key, _flag, kind in _OPTIONS:
            value = getattr(self, attr)
            if kind in ("list", "path-list"):
                data[key] = [str(item) for item in value]
            elif value is not None:
                data[key] = str(value)
        return data

    @classmethod
    def from_toml(cls, data: dict[str, Any]) -> SetupOptions:
        """Construct from a TOML table produced by `to_toml()`.

        :raises InvalidProjectError: if any value has the wrong type.
        """
        kwargs: dict[str, Any] = {}
        for attr, key, _flag, kind in _OPTIONS:
            value = data.get(key)
            if kind in ("list", "path-list"):
                if value is None:
                    value = []
                if not isinstance(value, list) or not all(
                    isinstance(item, str) for item in value
                ):
                    raise InvalidProjectError(
                        f"option {key!r} must be a list of strings"
                    )
                kwargs[attr] = (
                    [Path(item) for item in value] if kind == "path-list" else value
                )
            elif value is None:
                kwargs[attr] = None
            elif not isinstance(value, str):
                raise InvalidProjectError(f"option {key!r} must be a string")
            else:
                kwargs[attr] = Path(value) if kind == "path" else value
        return cls(**kwargs)


@dataclass
class ProjectConfig:
    """The recorded configuration of an xpython work directory."""

    platform: str
    options: SetupOptions


def write_project(work_path: Path, config: ProjectConfig) -> None:
    """Write the project file into a work directory.

    :param work_path: The work directory.
    :param config: The configuration to record.
    """
    data = {
        "schema": SCHEMA_VERSION,
        "xpython-version": xpython.__version__,
        "platform": config.platform,
        "options": config.options.to_toml(),
    }
    with (work_path / PROJECT_FILENAME).open("wb") as f:
        tomli_w.dump(data, f)


def read_project(work_path: Path) -> ProjectConfig:
    """Read the project file from a work directory.

    :param work_path: The work directory.
    :returns: The recorded configuration.
    :raises InvalidProjectError: if the project file is missing or invalid.
    """
    path = work_path / PROJECT_FILENAME
    if not path.is_file():
        raise InvalidProjectError(f"{PROJECT_FILENAME} not found")

    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise InvalidProjectError(f"{PROJECT_FILENAME} could not be parsed: {e}") from e

    schema = data.get("schema")
    if isinstance(schema, bool) or schema != SCHEMA_VERSION:
        raise InvalidProjectError(f"unsupported {PROJECT_FILENAME} schema {schema!r}")

    platform = data.get("platform")
    if platform not in PLATFORMS:
        raise InvalidProjectError(f"unknown platform {platform!r}")

    options = data.get("options")
    if not isinstance(options, dict):
        raise InvalidProjectError("missing [options] table")

    return ProjectConfig(platform=platform, options=SetupOptions.from_toml(options))


def _display(value: Any) -> str:
    if value is None:
        return "(not set)"
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def option_discrepancies(
    recorded: SetupOptions,
    given: SetupOptions,
) -> list[tuple[str, str, str]]:
    """Find setup options that were explicitly given but differ from the
    recorded options.

    An option is "explicitly given" if it is not `None` or an empty list.

    :param recorded: The options recorded in the project file.
    :param given: The options provided on the command line.
    :returns: A list of `(cli_flag, recorded_display, given_display)` tuples,
        in option order.
    """
    discrepancies = []
    for attr, _key, flag, _kind in _OPTIONS:
        given_value = getattr(given, attr)
        if given_value is None or given_value == []:
            continue
        recorded_value = getattr(recorded, attr)
        if given_value != recorded_value:
            discrepancies.append(
                (flag, _display(recorded_value), _display(given_value))
            )
    return discrepancies
