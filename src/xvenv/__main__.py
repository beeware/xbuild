from __future__ import annotations

import sys
import venv
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from build.__main__ import _error

import xvenv
from xvenv.convert import convert_venv
from xvenv.fetch import fetch_python, resolve_arch, resolve_cache_dir


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
    # --platform. Exactly one of these arguments must be provided.
    config_group = parser.add_mutually_exclusive_group(required=True)
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
    parser.add_argument(
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

    venv_path = Path(args.venv).resolve()
    build_details_path = (
        Path(args.build_details_path).resolve() if args.build_details_path else None
    )
    sysconfigdata_path = (
        Path(args.sysconfigdata_path).resolve() if args.sysconfigdata_path else None
    )

    if not venv_path.exists():
        venv.create(venv_path, with_pip=args.with_pip)

    try:
        if args.platform is not None:
            cache_dir = resolve_cache_dir(args.cache)
            arch = resolve_arch(args.platform, args.arch)

            config_path, is_build_details = fetch_python(args.platform, arch, cache_dir)
            if is_build_details:
                build_details_path = config_path
            else:
                sysconfigdata_path = config_path

        convert_venv(
            venv_path,
            build_details_path=build_details_path,
            sysconfigdata_path=sysconfigdata_path,
        )
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
