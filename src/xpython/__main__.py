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
from xpython.project import (
    InvalidProjectError,
    ProjectConfig,
    SetupOptions,
    option_discrepancies,
    read_project,
    write_project,
)
from xvenv.args import MISSING_CONFIG_ERROR, make_common_parser, parse_common_args
from xvenv.convert import CrossVenvConfig, in_cross_env, run_testbed


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
            "xpython exits. If the directory was set up by a previous "
            "xpython invocation, the existing testbed project is reused."
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

    If `--work-dir` names an existing directory, it must contain a project
    file written by a previous successful xpython invocation; the
    recorded project is stored as `args.project`, and its platform is used
    as the target platform. Otherwise, `args.project` is `None`.

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

    args = parse_common_args(parser, xpython_args, require_config=False)

    args.project = None
    if args.work_path is not None:
        args.work_path = args.work_path.resolve()
        if args.work_path.exists():
            try:
                args.project = read_project(args.work_path)
            except InvalidProjectError as e:
                _error(
                    f"Working directory `{args.work_path}` exists, but is not a "
                    f"valid xpython work directory ({e}). Delete it, or choose a "
                    "different --work-dir."
                )

    if args.project is not None:
        # Reusing an existing project; the recorded platform is the target.
        target_platform = args.project.platform
    elif args.use_current_env:
        if not in_cross_env():
            parser.error(MISSING_CONFIG_ERROR)
        # In a cross-platform environment, sys.platform is the target platform.
        target_platform = sys.platform
    else:
        target_platform = args.platform

    if args.simulator is not None and target_platform != "ios":
        parser.error("--simulator option also requires --platform ios")
    if args.managed is not None and target_platform != "android":
        parser.error("--managed option also requires --platform android")
    if args.connected is not None and target_platform != "android":
        parser.error("--connected option also requires --platform android")

    args.forwarded_args = forwarded_args

    return args


def main(cli_args: Sequence[str]) -> None:
    """Parse the CLI arguments and run the module in the target testbed.

    :param cli_args: CLI arguments
    """
    parser = main_parser()
    args = _parse_args(parser, cli_args)

    try:
        if args.project is not None:
            exit_code = _reuse(args)
        elif args.work_path is not None:
            args.work_path.mkdir(parents=True)
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

    # Record the project configuration only once setup has fully succeeded,
    # so that a partially configured work directory can't be reused.
    write_project(
        args.work_path,
        ProjectConfig(
            platform=cross_venv.platform,
            options=SetupOptions.from_args(args),
        ),
    )

    _cprint("{bold}Running testbed...{reset}")
    return cross_venv.run_testbed(
        work_path=args.work_path,
        args=args.forwarded_args,
        simulator=args.simulator,
        managed=args.managed,
        connected=args.connected,
        verbose=args.verbosity,
    )


def _reuse(args: argparse.Namespace) -> int:
    """Run the testbed of an existing, already-configured work directory.

    No setup is performed. Any setup options that were provided and differ
    from the options used to configure the work directory are ignored, with
    a warning.

    :param args: The parsed CLI namespace, with `project` set to the
        configuration recorded in `work_path`.
    :returns: The exit code to propagate from `main()`.
    """
    project = args.project
    _cprint("{bold}Reusing testbed project in {}...{reset}", str(args.work_path))

    for flag, recorded, given in option_discrepancies(
        project.options, SetupOptions.from_args(args)
    ):
        _cprint(
            "{yellow}WARNING{reset} {}",
            f"Ignoring {flag} {given}; {args.work_path} was configured with "
            f"{flag} {recorded}.",
            file=sys.stderr,
        )

    _cprint("{bold}Running testbed...{reset}")
    return run_testbed(
        project.platform,
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
