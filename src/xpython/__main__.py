from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from build.__main__ import _cprint, _error, _setup_cli

import xpython
from xpython.deps import install_requirements, resolve_requirements
from xvenv.args import make_common_parser, parse_common_args
from xvenv.convert import CrossVenvConfig


def main_parser() -> argparse.ArgumentParser:
    parser = make_common_parser(
        "xpython",
        description=(
            "Run a Python module inside an iOS Simulator or Android "
            "emulator/device testbed, without needing to build a wheel."
        ),
        version=f"xpython {xpython.__version__}",
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
        "-f",
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
        dest="work_path",
        type=Path,
        help=(
            "Use this directory for the cross-venv, dependency install, "
            "and testbed staging, instead of a temporary directory. Unlike "
            "a temporary directory, this directory is NOT deleted when "
            "xpython exits."
        ),
    )
    return parser


def _parse_args(
    parser: argparse.ArgumentParser,
    cli_args: Sequence[str],
) -> argparse.Namespace:
    """Parse and validate CLI arguments, including the `--` separator
    split and platform-specific forwarded-argument handling.

    Everything before the first literal `"--"` in `cli_args` is parsed as
    `xpython`'s own flags. Everything after it is treated as a raw,
    unparsed list of forwarded arguments: for an iOS target, the first
    forwarded argument must be `-m` (stripped, then split into
    `args.module`/`args.module_args`); for an Android target, the
    forwarded arguments are stored verbatim as `args.forwarded_args`, with
    no validation.

    If none of `--platform`/`--build-details`/`--sysconfig` is given, the
    current cross-platform environment is used (`args.use_current_env` is
    `True`); this is an error if not running in a cross-platform environment.

    If `"--"` is absent from `cli_args` entirely, the forwarded-argument
    list is treated as empty (not an error).

    :param parser: The full argument parser
    :param cli_args: CLI arguments
    :param prog: Program name to show in help text
    :returns: The parsed, validated, and platform-annotated namespace.
    :raises SystemExit: via `parser.error(...)` (exit code 2) for any
        invalid flag combination, including a non-`-m` first forwarded
        argument on iOS.
    """
    try:
        separator_index = cli_args.index("--")
        xpython_args = cli_args[:separator_index]
        forwarded_args = list(cli_args[separator_index + 1 :])
    except ValueError:
        xpython_args = cli_args
        forwarded_args = []

    args = parse_common_args(parser, xpython_args)

    if args.use_current_env:
        # In a cross-platform environment, sys.platform is the target platform.
        target_platform = sys.platform
    else:
        target_platform = args.platform

    if args.simulator is not None and target_platform != "ios":
        parser.error("--simulator requires --platform ios")
    if args.managed is not None and target_platform != "android":
        parser.error("--managed requires --platform android")
    if args.connected is not None and target_platform != "android":
        parser.error("--connected requires --platform android")

    args.forwarded_args = forwarded_args

    return args


def main(cli_args: Sequence[str]) -> None:
    """Parse the CLI arguments and run the module in the target testbed.

    :param cli_args: CLI arguments
    """
    parser = main_parser()
    args = _parse_args(parser, cli_args)

    _setup_cli(verbosity=args.verbosity)

    try:
        if args.work_path is not None:
            if args.work_path.exists():
                _error(f"Working directory `{args.work_path}` already exists.")

            args.work_path.mkdir(parents=True, exist_ok=True)
            exit_code = _run(args)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                args.work_path = Path(tmp)
                exit_code = _run(args)
    except (ValueError, NotImplementedError) as e:
        _error(e)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        _error(f"Failed to set up the testbed environment: {e}")
        sys.exit(1)

    sys.exit(exit_code)


def _run(args: argparse.Namespace) -> int:
    """Run the full create-venv/create/install-deps/run pipeline for an
    already-validated, already-parsed set of arguments.

    :param args: The parsed CLI namespace, with `work_path` resolved to an
        existing directory (either `--work-dir` or a temp dir).
    :returns: The exit code to propagate from `main()`.
    """
    _cprint("{bold}Creating cross-venv...{reset}")
    venv_path = args.work_path / "venv"
    if args.use_current_env:
        cross_venv = CrossVenvConfig.from_current_env()
    else:
        cross_venv = CrossVenvConfig(
            platform=args.platform,
            arch=args.arch,
            archive_path=args.archive,
            build_details_path=args.build_details_path,
            sysconfigdata_path=args.sysconfigdata_path,
            cache_path=args.cache,
        )

    cross_venv.create(venv_path, with_pip=True)

    _cprint("{bold}Creating testbed project...{reset}")
    cross_venv.setup_testbed(
        work_path=args.work_path,
        src_paths=args.src,
    )

    _cprint("{bold}Installing dependencies...{reset}")
    requirements = resolve_requirements(
        args.dependencies, args.groups, Path("pyproject.toml")
    )
    packages_path = cross_venv.packages_path(args.work_path)
    packages_path.mkdir(parents=True, exist_ok=True)
    if requirements:
        venv_python = venv_path / "bin" / "python3"
        install_requirements(venv_python, requirements, packages_path, args.find_links)

    _cprint("{bold}Running testbed...{reset}")
    return cross_venv.run_testbed(
        work_path=args.work_path,
        args=args.forwarded_args,
        simulator=args.simulator,
        managed=args.managed,
        connected=args.connected,
        verbose=args.verbosity,
    )


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
