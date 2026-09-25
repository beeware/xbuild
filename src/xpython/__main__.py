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
from xpython.platforms import android as android_platform
from xpython.platforms import emscripten as emscripten_platform
from xpython.platforms import ios as ios_platform
from xvenv.convert import create_cross_venv


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
            "The target architecture. Defaults to a useful value based on "
            "the host machine's architecture."
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


def _parse_args(cli_args: Sequence[str], prog: str | None = None) -> argparse.Namespace:
    """Parse and validate CLI arguments, including the `--` separator
    split and platform-specific forwarded-argument handling.

    Everything before the first literal `"--"` in `cli_args` is parsed as
    `xpython`'s own flags. Everything after it is treated as a raw,
    unparsed list of forwarded arguments: for `--platform ios`, the first
    forwarded argument must be `-m` (stripped, then split into
    `args.module`/`args.module_args`); for `--platform android`, the
    forwarded arguments are stored verbatim as `args.forwarded_args`, with
    no validation.

    If `"--"` is absent from `cli_args` entirely, the forwarded-argument
    list is treated as empty (not an error).

    :param cli_args: CLI arguments
    :param prog: Program name to show in help text
    :returns: The parsed, validated, and platform-annotated namespace.
    :raises SystemExit: via `parser.error(...)` (exit code 2) for any
        invalid flag combination, including a non-`-m` first forwarded
        argument on iOS.
    """
    parser = main_parser()
    if prog:
        parser.prog = prog

    try:
        separator_index = cli_args.index("--")
        xpython_args = cli_args[:separator_index]
        forwarded_args = list(cli_args[separator_index + 1 :])
    except ValueError:
        xpython_args = cli_args
        forwarded_args = []

    args = parser.parse_args(xpython_args)

    if args.arch is not None and args.platform is None:
        parser.error("--arch requires --platform")
    if args.cache is not None and args.platform is None:
        parser.error("--cache requires --platform")

    if args.simulator is not None and args.platform != "ios":
        parser.error("--simulator requires --platform ios")
    if args.managed is not None and args.platform != "android":
        parser.error("--managed requires --platform android")
    if args.connected is not None and args.platform != "android":
        parser.error("--connected requires --platform android")

    args.forwarded_args = forwarded_args

    return args


def main(cli_args: Sequence[str], prog: str | None = None) -> None:
    """Parse the CLI arguments and run the module in the target testbed.

    :param cli_args: CLI arguments
    :param prog: Program name to show in help text
    """
    args = _parse_args(cli_args, prog)

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
    result = create_cross_venv(
        venv_path,
        platform=args.platform,
        arch=args.arch,
        build_details_path=args.build_details_path,
        sysconfigdata_path=args.sysconfigdata_path,
        cache_path=args.cache,
        with_pip=True,
    )

    platform_module = {
        "android": android_platform,
        "ios": ios_platform,
        "emscripten": emscripten_platform,
    }[result.platform.lower()]

    _cprint("{bold}Creating testbed project...{reset}")
    platform_module.setup(
        archive_path=result.archive_path,
        work_path=args.work_path,
        src_paths=args.src,
    )

    _cprint("{bold}Installing dependencies...{reset}")
    requirements = resolve_requirements(
        args.dependencies, args.groups, Path("pyproject.toml")
    )
    packages_path = platform_module.packages_path(args.work_path)
    packages_path.mkdir(parents=True, exist_ok=True)
    if requirements:
        venv_python = venv_path / "bin" / "python3"
        install_requirements(venv_python, requirements, packages_path, args.find_links)

    _cprint("{bold}Running testbed...{reset}")
    return platform_module.run(
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
    main(sys.argv[1:], "python -m xpython")


__all__ = [
    "main",
    "main_parser",
]
