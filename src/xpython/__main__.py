from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import xpython


def main_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        "xpython",
        description=(
            "Run a Python module inside an iOS Simulator or Android "
            "emulator/device testbed, without needing to build a wheel."
        ),
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"xpython {xpython.__version__}",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="increase verbosity",
    )
    parser.add_argument(
        "--platform",
        dest="platform",
        choices=["ios", "android"],
        required=True,
        help="The target platform to run the module on.",
    )
    parser.add_argument(
        "--arch",
        dest="arch",
        help=(
            "The target architecture. Defaults to a useful value based on "
            "the host machine's architecture."
        ),
    )
    parser.add_argument(
        "--cache",
        dest="cache",
        type=Path,
        help=(
            "The directory to use for caching downloaded Python builds. "
            "Defaults to the XBUILD_CACHE environment variable, or a "
            "platform-appropriate cache directory."
        ),
    )
    parser.add_argument(
        "--dependency",
        "-d",
        dest="dependencies",
        action="append",
        default=[],
        metavar="SPEC",
        help=(
            "A PEP 508 dependency specifier to install into the testbed "
            "(e.g. 'requests', 'attrs>=23'). Can be repeated."
        ),
    )
    parser.add_argument(
        "--group",
        dest="groups",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "The name of a PEP 735 dependency group (from "
            "[dependency-groups] in ./pyproject.toml) to install into the "
            "testbed. Can be repeated."
        ),
    )
    parser.add_argument(
        "--find-links",
        dest="find_links",
        action="append",
        default=[],
        metavar="DIR",
        help=(
            "A directory of local wheels to prefer during dependency "
            "resolution, forwarded to pip's --find-links. Can be repeated."
        ),
    )
    parser.add_argument(
        "--src",
        dest="src",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help=(
            "A path to copy into the testbed's working directory (e.g. a "
            "test suite). Can be repeated."
        ),
    )
    parser.add_argument(
        "--simulator",
        dest="simulator",
        help=(
            "The name of the iOS simulator to use (e.g. 'iPhone 16e'). "
            "Only valid with --platform ios."
        ),
    )
    device_group = parser.add_mutually_exclusive_group()
    device_group.add_argument(
        "--managed",
        dest="managed",
        metavar="NAME",
        help=(
            "The name of a Gradle-managed Android device to use (default: "
            "'maxVersion' if neither --managed nor --connected is given). "
            "Only valid with --platform android."
        ),
    )
    device_group.add_argument(
        "--connected",
        dest="connected",
        metavar="SERIAL",
        help=(
            "The serial number of an already-connected Android device to "
            "use. Only valid with --platform android."
        ),
    )
    parser.add_argument(
        "--work-dir",
        dest="work_dir",
        type=Path,
        help=(
            "Use this directory for the cross-venv, dependency install, "
            "and testbed staging, instead of a temporary directory. Unlike "
            "a temporary directory, this directory is NOT deleted when "
            "xpython exits."
        ),
    )
    parser.add_argument(
        "-m",
        dest="module_and_args",
        nargs=argparse.REMAINDER,
        required=True,
        metavar="MODULE [arg ...]",
        help="The module to run, and any arguments to pass to it.",
    )
    return parser


def main(cli_args: Sequence[str], prog: str | None = None) -> None:
    """Parse the CLI arguments and run the module in the target testbed.

    :param cli_args: CLI arguments
    :param prog: Program name to show in help text
    """
    parser = main_parser()
    if prog:
        parser.prog = prog
    args = parser.parse_args(cli_args)

    if args.simulator is not None and args.platform != "ios":
        parser.error("--simulator requires --platform ios")
    if args.managed is not None and args.platform != "android":
        parser.error("--managed requires --platform android")
    if args.connected is not None and args.platform != "android":
        parser.error("--connected requires --platform android")
    if not args.module_and_args:
        parser.error("the following arguments are required: -m")

    args.module = args.module_and_args[0]
    args.module_args = args.module_and_args[1:]

    # Task 6 fills in the rest of main()'s body: create_cross_venv(),
    # dependency resolution/install, and platform dispatch.


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:], "python -m xpython")


__all__ = [
    "main",
    "main_parser",
]
