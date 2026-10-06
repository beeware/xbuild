import argparse
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from xvenv.convert import in_cross_env


def make_common_parser(
    cmd: str,
    description: str,
    version: str,
) -> argparse.ArgumentParser:
    """Create a base parser with all common xvenv options.

    :param cmd: The command parser to extend with common arguments.
    :param description: A description of the command to be executed.
    :param version: The version string to show to the user.
    :returns: A new parser object.
    """
    make_parser = partial(
        argparse.ArgumentParser,
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    if sys.version_info >= (3, 14):
        make_parser = partial(make_parser, suggest_on_error=True)

    parser = make_parser(cmd)
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=version,
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

    return parser


def parse_common_args(
    parser: argparse.ArgumentParser,
    cli_args: Sequence[str],
) -> argparse.Namespace:
    """Perform initial parsing and validation of common arguments.

    :param parser: The complete parser to use.
    :param cli_args: The command line arguments to parse.
    :returns: The namespace of parsed arguments.
    """
    args = parser.parse_args(cli_args)

    if args.arch is not None and args.platform is None:
        parser.error("--arch requires --platform")
    if args.cache is not None and args.platform is None:
        parser.error("--cache requires --platform")
    if args.archive is not None and args.platform is None:
        parser.error("--archive requires --platform")

    args.use_current_env = all(
        value is None
        for value in (args.platform, args.build_details_path, args.sysconfigdata_path)
    )
    if args.use_current_env and not in_cross_env():
        parser.error(
            "one of the arguments --build-details --sysconfig --platform is required"
        )

    return args
