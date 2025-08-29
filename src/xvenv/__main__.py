from __future__ import annotations

import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from build.__main__ import (
    _cprint,
    _error,
)

import xvenv
from xvenv.convert import convert_venv


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
    parser.add_argument(
        "-s",
        "--sysconfig",
        help="The path to a sysconfig_vars JSON file or sysconfigdata Python file",
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

    venv_path = Path(args.venv).resolve()
    sysconfig_path = Path(args.sysconfig).resolve()

    if not venv_path.exists():
        _error(f"Native virtual environment {venv_path} does not exist.")
    else:
        try:
            description = convert_venv(venv_path, sysconfig_path)
        except Exception as e:
            _error(e)
            sys.exit(1)
        else:
            _cprint(
                "{bold}{green}{}{reset}",
                f"{args.venv} is now an {description} cross venv.",
            )


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:], "python -m build")

__all__ = [
    "main",
    "main_parser",
]
