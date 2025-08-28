from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from functools import partial

from build import ProjectBuilder
from build import env as _env
from build.__main__ import (
    _cprint,
    _handle_build_error,
    _max_terminal_width,
    _natural_language_list,
    _setup_cli,
    _styles,
)
from build._types import ConfigSettings, Distribution, StrPath
from build.env import DefaultIsolatedEnv

import xbuild


def _build_in_isolated_env(
    srcdir: StrPath,
    outdir: StrPath,
    distribution: Distribution,
    config_settings: ConfigSettings | None,
    installer: _env.Installer,
) -> str:
    with DefaultIsolatedEnv(installer=installer) as env:
        builder = ProjectBuilder.from_isolated_env(env, srcdir)
        # first install the build dependencies
        env.install(builder.build_system_requires)
        # then get the extra required dependencies from the backend
        # (which was installed in the call above :P)
        env.install(builder.get_requires_for_build(distribution, config_settings or {}))
        return builder.build(distribution, outdir, config_settings or {})


def main_parser() -> argparse.ArgumentParser:
    """Construct the main parser."""
    formatter_class = partial(
        argparse.RawDescriptionHelpFormatter, width=min(_max_terminal_width, 127)
    )
    # Workaround for 3.14.0 beta 1, can remove once beta 2 is out
    if sys.version_info >= (3, 14):
        formatter_class = partial(formatter_class, color=True)

    make_parser = partial(
        argparse.ArgumentParser,
        description="A cross-platform build backend for Python",
        # Prevent argparse from taking up the entire width of the terminal window
        # which impedes readability. Also keep the description formatted.
        formatter_class=formatter_class,
    )
    if sys.version_info >= (3, 14):
        make_parser = partial(make_parser, suggest_on_error=True, color=True)

    parser = make_parser()
    parser.add_argument(
        "srcdir",
        type=str,
        nargs="?",
        default=os.getcwd(),
        help="source directory (defaults to current directory)",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"xbuild {xbuild.__version__} ({','.join(xbuild.__path__)})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="increase verbosity",
    )
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
    # parser.add_argument(
    #     "--skip-dependency-check",
    #     "-x",
    #     action="store_true",
    #     help="do not check that build dependencies are installed",
    # )
    # env_group = parser.add_mutually_exclusive_group()
    # env_group.add_argument(
    #     "--no-isolation",
    #     "-n",
    #     action="store_true",
    #     help="disable building the project in an isolated virtual environment. "
    #     "Build dependencies must be installed separately when this option is used",
    # )
    # env_group.add_argument(
    #     "--installer",
    #     choices=_env.INSTALLERS,
    #     help="Python package installer to use (defaults to pip)",
    # )
    # config_group = parser.add_mutually_exclusive_group()
    # config_group.add_argument(
    #     "--config-setting",
    #     "-C",
    #     dest="config_settings",
    #     action="append",
    #     help=(
    #         "settings to pass to the backend.  Multiple settings can be "
    #         "provided. Settings beginning with a hyphen will erroneously "
    #         "be interpreted as options to build if separated by a space "
    #         "character; use ``--config-setting=--my-setting -C--my-other-setting``"
    #     ),
    #     metavar="KEY[=VALUE]",
    # )
    # config_group.add_argument(
    #     "--config-json",
    #     dest="config_json",
    #     help=(
    #         "settings to pass to the backend as a JSON object. This is an "
    #         "alternative to --config-setting that allows complex nested "
    #         "structures. Cannot be used together with --config-setting"
    #     ),
    #     metavar="JSON_STRING",
    # )

    return parser


def main(cli_args: Sequence[str], prog: str | None = None) -> None:
    """Parse the CLI arguments and invoke the build process.

    :param cli_args: CLI arguments
    :param prog: Program name to show in help text
    """
    parser = main_parser()
    if prog:
        parser.prog = prog
    args = parser.parse_args(cli_args)

    _setup_cli(verbosity=args.verbosity)

    config_settings = {}

    # # Handle --config-json
    # if args.config_json:
    #     try:
    #         config_settings = json.loads(args.config_json)
    #         if not isinstance(config_settings, dict):
    #             _error(
    #                 "--config-json must contain a JSON object (dict), "
    #                 "not a list or primitive value"
    #             )
    #     except json.JSONDecodeError as e:
    #         _error(f"Invalid JSON in --config-json: {e}")

    # # Handle --config-setting (original logic)
    # elif args.config_settings:
    #     for arg in args.config_settings:
    #         setting, _, value = arg.partition("=")
    #         if setting not in config_settings:
    #             config_settings[setting] = value
    #         else:
    #             if not isinstance(config_settings[setting], list):
    #                 config_settings[setting] = [config_settings[setting]]

    #             config_settings[setting].append(value)

    # outdir is relative to srcdir only if omitted.
    outdir = os.path.join(args.srcdir, "dist") if args.outdir is None else args.outdir

    with _handle_build_error():
        built = [
            _build_in_isolated_env(
                args.srcdir,
                outdir,
                "wheel",
                config_settings,
                "pip",
            )
        ]
        artifact_list = _natural_language_list(
            [
                "{underline}{}{reset}{bold}{green}".format(artifact, **_styles.get())
                for artifact in built
            ]
        )
        _cprint("{bold}{green}Successfully built {}{reset}", artifact_list)


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:], "python -m build")

__all__ = [
    "main",
    "main_parser",
]
