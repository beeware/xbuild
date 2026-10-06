from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from build.__main__ import _error, _setup_cli

import xvenv
from xvenv.args import make_common_parser, parse_common_args
from xvenv.convert import CrossVenvConfig


def main_parser():
    parser = make_common_parser(
        "xvenv",
        description=(
            "Convert a native virtual environment into a cross-platform "
            "virtual environment."
        ),
        version=f"xvenv {xvenv.__version__}",
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


def main(cli_args: Sequence[str]) -> None:
    """Parse the CLI arguments and convert the venv.

    :param cli_args: CLI arguments
    """
    parser = main_parser()
    args = parse_common_args(parser, cli_args)

    _setup_cli(verbosity=args.verbosity)

    venv_path = Path(args.venv).resolve()

    try:
        if args.use_current_env:
            cross_venv = CrossVenvConfig.from_current_env()
        else:
            cross_venv = CrossVenvConfig(
                platform=args.platform,
                arch=args.arch,
                build_details_path=args.build_details_path,
                sysconfigdata_path=args.sysconfigdata_path,
                cache_path=args.cache,
                archive_path=args.archive,
            )

        cross_venv.create(venv_path, with_pip=args.with_pip)
    except (ValueError, NotImplementedError) as e:
        _error(e)
        sys.exit(1)


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
