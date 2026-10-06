from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from build import env as _env
from build.__main__ import (
    _cprint,
    _error,
    _handle_build_error,
    _natural_language_list,
    _setup_cli,
    _styles,
)
from build._types import ConfigSettings, Distribution, StrPath
from build._util import _format_dep_chain

import xbuild
from xbuild._builder import ProjectXBuilder
from xbuild.env import XBuildIsolatedEnv
from xvenv.args import make_common_parser, parse_common_args
from xvenv.convert import CrossVenvConfig


def _build(
    isolation: bool,
    srcdir: StrPath,
    outdir: StrPath,
    distribution: Distribution,
    config_settings: ConfigSettings | None,
    skip_dependency_check: bool,
    installer: _env.Installer,
    cross_venv: CrossVenvConfig,
) -> str:
    if isolation:
        return _build_in_isolated_env(
            srcdir,
            outdir,
            distribution,
            config_settings,
            installer,
            cross_venv,
        )
    else:
        return _build_in_current_env(
            srcdir,
            outdir,
            distribution,
            config_settings,
            skip_dependency_check,
        )


def _build_in_isolated_env(
    srcdir: StrPath,
    outdir: StrPath,
    distribution: Distribution,
    config_settings: ConfigSettings | None,
    installer: _env.Installer,
    cross_venv: CrossVenvConfig,
) -> str:
    with XBuildIsolatedEnv(
        installer=installer,
        cross_venv=cross_venv,
    ) as env:
        builder = ProjectXBuilder.from_isolated_env(env, srcdir)

        # First install the dependencies for the build
        env.install(builder.build_system_requires, for_target=False)

        # then get the extra required dependencies from the backend
        # (which was installed in the call above :P)
        env.install(
            builder.get_requires_for_build(distribution, config_settings or {}),
            for_target=False,
        )

        # Repeat this process for target dependencies
        env.install(builder.build_system_target_requires)
        # then get the extra required target dependencies from the backend
        env.install(
            builder.get_target_requires_for_build(distribution, config_settings or {})
        )

        # Now run the build
        return builder.build(distribution, outdir, config_settings or {})


def _build_in_current_env(
    srcdir: StrPath,
    outdir: StrPath,
    distribution: Distribution,
    config_settings: ConfigSettings | None,
    skip_dependency_check: bool = False,
) -> str:
    builder = ProjectXBuilder(srcdir)

    if not skip_dependency_check:
        missing = builder.check_dependencies(distribution, config_settings or {})
        if missing:
            dependencies = "".join(
                "\n\t" + dep
                for deps in missing
                for dep in (deps[0], _format_dep_chain(deps[1:]))
                if dep
            )
            _cprint()
            _error(f"Missing build dependencies:{dependencies}")

        missing = builder.check_target_dependencies(distribution, config_settings or {})
        if missing:
            dependencies = "".join(
                "\n\t" + dep
                for deps in missing
                for dep in (deps[0], _format_dep_chain(deps[1:]))
                if dep
            )
            _cprint()
            _error(f"Missing target build dependencies:{dependencies}")

    return builder.build(distribution, outdir, config_settings or {})


def main_parser() -> argparse.ArgumentParser:
    """Construct the main parser."""
    parser = make_common_parser(
        "xbuild",
        description="A cross-platform build backend for Python",
        version=f"xbuild {xbuild.__version__} ({','.join(xbuild.__path__)})",
    )

    parser.add_argument(
        "srcdir",
        type=str,
        nargs="?",
        default=os.getcwd(),
        help="source directory (defaults to current directory)",
    )

    ## xbuild doesn't need to produce sdists, which makes --wheel redundant
    # parser.add_argument(
    #     "--sdist",
    #     "-s",
    #     dest="distributions",
    #     action="append_const",
    #     const="sdist",
    #     help="build a source distribution (disables the default behavior)",
    # )
    # parser.add_argument(
    #     "--wheel",
    #     "-w",
    #     dest="distributions",
    #     action="append_const",
    #     const="wheel",
    #     help="build a wheel (disables the default behavior)",
    # )
    parser.add_argument(
        "--outdir",
        "-o",
        type=str,
        help=f"output directory (defaults to {{srcdir}}{os.sep}dist)",
        metavar="PATH",
    )
    parser.add_argument(
        "--skip-dependency-check",
        "-x",
        action="store_true",
        help="do not check that build dependencies are installed",
    )
    env_group = parser.add_mutually_exclusive_group()
    env_group.add_argument(
        "--no-isolation",
        "-n",
        action="store_true",
        help=(
            "disable building the project in an isolated virtual environment. "
            "Build dependencies must be installed separately when this option is used"
        ),
    )
    env_group.add_argument(
        "--installer",
        choices=_env.INSTALLERS,
        help="Python package installer to use (defaults to pip)",
    )

    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--config-setting",
        "-C",
        dest="config_settings",
        action="append",
        help=(
            "settings to pass to the backend.  Multiple settings can be "
            "provided. Settings beginning with a hyphen will erroneously "
            "be interpreted as options to build if separated by a space "
            "character; use ``--config-setting=--my-setting -C--my-other-setting``"
        ),
        metavar="KEY[=VALUE]",
    )
    config_group.add_argument(
        "--config-json",
        dest="config_json",
        help=(
            "settings to pass to the backend as a JSON object. This is an "
            "alternative to --config-setting that allows complex nested "
            "structures. Cannot be used together with --config-setting"
        ),
        metavar="JSON_STRING",
    )

    return parser


def main(cli_args: Sequence[str]) -> None:
    """Parse the CLI arguments and invoke the build process.

    :param cli_args: CLI arguments
    """
    parser = main_parser()
    args = parse_common_args(parser, cli_args)

    _setup_cli(verbosity=args.verbosity)

    try:
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

        os.environ.update(cross_venv.prepare_env())
    except (ValueError, NotImplementedError) as e:
        _error(e)
        sys.exit(1)

    config_settings = {}

    # Handle --config-json
    if args.config_json:
        try:
            config_settings = json.loads(args.config_json)
            if not isinstance(config_settings, dict):
                _error(
                    "--config-json must contain a JSON object (dict), "
                    "not a list or primitive value"
                )
        except json.JSONDecodeError as e:
            _error(f"Invalid JSON in --config-json: {e}")

    # Handle --config-setting (original logic)
    elif args.config_settings:
        for arg in args.config_settings:
            setting, _, value = arg.partition("=")
            if setting not in config_settings:
                config_settings[setting] = value
            else:
                if not isinstance(config_settings[setting], list):
                    config_settings[setting] = [config_settings[setting]]

                config_settings[setting].append(value)

    # outdir is relative to srcdir only if omitted.
    outdir = os.path.join(args.srcdir, "dist") if args.outdir is None else args.outdir

    with _handle_build_error(env_dir=None, sdist_extract_dir=None):
        built = [
            _build(
                not args.no_isolation,
                args.srcdir,
                outdir,
                "wheel",
                config_settings,
                args.skip_dependency_check,
                args.installer,
                cross_venv,
            )
        ]
        artifact_list = _natural_language_list(
            [
                "{underline}{}{reset}{bold}{green}".format(
                    artifact, **_styles.get()["stdout"]
                )
                for artifact in built
            ]
        )
        _cprint("{bold}{green}Successfully built {}{reset}", artifact_list)


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
