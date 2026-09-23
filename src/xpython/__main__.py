from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from build.__main__ import _cprint, _error

import xpython
from xpython.deps import install_requirements, resolve_requirements
from xpython.platforms.android import stage_and_run as android_stage_and_run
from xpython.platforms.ios import stage_and_run as ios_stage_and_run
from xvenv.api import create_cross_venv


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

    try:
        if args.work_dir is not None:
            args.work_dir.mkdir(parents=True, exist_ok=True)
            exit_code = _run(args)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                args.work_dir = Path(tmp)
                exit_code = _run(args)
    except (ValueError, NotImplementedError) as e:
        _error(e)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        _error(f"Failed to set up the testbed environment: {e}")
        sys.exit(1)

    sys.exit(exit_code)


def _run(args: argparse.Namespace) -> int:
    """Run the full create-venv/install-deps/stage-and-run pipeline for an
    already-validated, already-parsed set of arguments.

    :param args: The parsed CLI namespace, with `work_dir` resolved to an
        existing directory (either `--work-dir` or a temp dir).
    :returns: The exit code to propagate from `main()`.
    """
    _cprint("{bold}Creating cross-venv...{reset}")
    venv_path = args.work_dir / "venv"
    result = create_cross_venv(venv_path, args.platform, args.arch, args.cache)

    requirements = resolve_requirements(
        args.dependencies, args.groups, Path("pyproject.toml")
    )

    packages_dir = args.work_dir / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    if requirements:
        _cprint("{bold}Installing dependencies...{reset}")
        venv_python = venv_path / "bin" / "python3"
        install_requirements(venv_python, requirements, packages_dir, args.find_links)

    if args.platform == "ios":
        return ios_stage_and_run(
            archive_dir=result.archive_dir,
            work_dir=args.work_dir,
            src_paths=args.src,
            packages_dir=packages_dir,
            module=args.module,
            module_args=args.module_args,
            simulator=args.simulator,
            verbose=args.verbosity,
        )
    else:
        return android_stage_and_run(
            archive_dir=result.archive_dir,
            work_dir=args.work_dir,
            src_paths=args.src,
            packages_dir=packages_dir,
            module=args.module,
            module_args=args.module_args,
            managed=args.managed,
            connected=args.connected,
            verbose=args.verbosity,
        )


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:], "python -m xpython")


__all__ = [
    "main",
    "main_parser",
]
