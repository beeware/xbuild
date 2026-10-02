from __future__ import annotations

import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from build.__main__ import _error, _setup_cli

import xvenv
from xvenv.convert import CrossVenvConfig, in_cross_env


def main_parser():
    parser = ArgumentParser(
        "xvenv",
        description=(
            "Convert a native virtual environment into a cross-platform "
            "virtual environment."
        ),
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"xvenv {xvenv.__version__}",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="increase verbosity",
    )

    # Create mutually exclusive group for --build-details, --sysconfig and
    # --platform. One of these arguments must be provided, unless xvenv is
    # running in a cross-platform environment, in which case the configuration
    # of the current environment is used by default.
    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--build-details",
        dest="build_details_path",
        type=Path,
        help="The path to a build-details.json file.",
    )
    config_group.add_argument(
        "--sysconfig",
        dest="sysconfigdata_path",
        type=Path,
        help="The path to a sysconfigdata python file.",
    )
    config_group.add_argument(
        "--platform",
        dest="platform",
        choices=["ios", "android", "emscripten"],
        help=(
            "Download (or reuse a cached copy of) a Python build for this "
            "target platform, matching the Python version currently "
            "running xvenv."
        ),
    )

    parser.add_argument(
        "--arch",
        dest="arch",
        help=(
            "The target architecture to use with --platform. Defaults to a "
            "useful value based on the host machine's architecture."
        ),
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--cache",
        dest="cache",
        type=Path,
        help=(
            "The directory to use for caching downloaded Python builds, "
            "for use with --platform. Defaults to the XBUILD_CACHE "
            "environment variable, or a platform-appropriate cache "
            "directory."
        ),
    )
    source_group.add_argument(
        "--archive",
        dest="archive",
        type=Path,
        help=(
            "Use an already-extracted Python build at this location "
            "instead of downloading one, for use with --platform. Must be "
            "laid out the same way an archive downloaded via --platform "
            "would have been unpacked."
        ),
    )
    parser.add_argument(
        "--without-pip",
        dest="with_pip",
        default=True,
        action="store_false",
        help=(
            "Skip installing pip when creating the virtual environment. "
            "Only relevant if the target venv doesn't already exist; "
            "matches python -m venv's --without-pip."
        ),
    )

    parser.add_argument(
        "venv",
        help="The location of a native virtual environment",
    )
    return parser


def main(cli_args: Sequence[str], prog: str | None = None) -> None:
    """Parse the CLI arguments and convert the venv.

    :param cli_args: CLI arguments
    :param prog: Program name to show in help text
    """
    parser = main_parser()
    if prog:
        parser.prog = prog
    args = parser.parse_args(cli_args)

    if args.arch is not None and args.platform is None:
        parser.error("--arch requires --platform")
    if args.cache is not None and args.platform is None:
        parser.error("--cache requires --platform")
    if args.archive is not None and args.platform is None:
        parser.error("--archive requires --platform")

    explicit_config = any(
        value is not None
        for value in (args.platform, args.build_details_path, args.sysconfigdata_path)
    )
    if not explicit_config and not in_cross_env():
        parser.error(
            "one of the arguments --build-details --sysconfig --platform is required"
        )

    _setup_cli(verbosity=args.verbosity)

    venv_path = Path(args.venv).resolve()

    try:
        if explicit_config:
            cross_venv = CrossVenvConfig(
                platform=args.platform,
                arch=args.arch,
                build_details_path=args.build_details_path,
                sysconfigdata_path=args.sysconfigdata_path,
                cache_path=args.cache,
                archive_path=args.archive,
            )
        else:
            cross_venv = CrossVenvConfig.from_current_env()
        cross_venv.create(venv_path, with_pip=args.with_pip)
    except (ValueError, NotImplementedError) as e:
        _error(e)
        sys.exit(1)


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:], "python -m xvenv")

__all__ = [
    "main",
    "main_parser",
]
