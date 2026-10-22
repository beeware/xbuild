from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from build import _builder, _ctx
from build._builder import ProjectBuilder, _parse_build_system_table
from build._types import ConfigSettings, Distribution, SubprocessRunner
from build._util import check_dependency

from xvenv.platforms import ACTIVE_COMPILER_WRAPPER_DIR_VAR, BUILD_ENV_SCRIPTS_DIR_VAR

if TYPE_CHECKING:
    from build.env import IsolatedEnv


###########################################################################
# A subprocess runner that keeps compiler wrappers at the front of PATH.
###########################################################################
def make_subprocess_runner(
    isolated_env: IsolatedEnv | None = None,
) -> SubprocessRunner:
    """Create the runner used to invoke build backend hooks.

    This is a slightly modified version of the default runner that pypa/build
    uses. pypa/build prepends the isolated environment's `bin` directory to
    PATH, which would shadow any compiler wrappers that a platform's
    `prepare_env()` installed (e.g., Emscripten's `cmake`/`meson` wrappers) if
    the same tools were installed as build dependencies. If a wrapper
    directory is in use, move it back to the front of PATH so the wrappers are
    found first, and tell the wrappers where the real build dependency tools
    live.

    :param isolated_env: The isolated build environment, or `None` if the
        build is running in the current environment.
    :returns: A pyproject-hooks compatible subprocess runner.
    """

    def _runner(
        cmd: Sequence[str],
        cwd: str | None = None,
        extra_environ: Mapping[str, str] | None = None,
    ) -> None:
        env = os.environ.copy()
        if extra_environ:
            env.update(extra_environ)

        if wrapper_dir := env.get(ACTIVE_COMPILER_WRAPPER_DIR_VAR):
            if isolated_env is not None:
                python = isolated_env.python_executable
            else:
                python = sys.executable
            env[BUILD_ENV_SCRIPTS_DIR_VAR] = str(Path(python).parent)

            # Move (rather than copy) the wrapper directory to the front.
            others = [
                part
                for part in env.get("PATH", "").split(os.pathsep)
                if part and part != wrapper_dir
            ]
            env["PATH"] = os.pathsep.join([wrapper_dir, *others])

        subprocess.run(cmd, cwd=cwd, env=env, check=True)

    return _runner


###########################################################################
# Patch `build._builder._parse_xbuild_system_table` so that it doesn't break
# in the presence of the `target-requires` setting.
###########################################################################
def parse_xbuild_system_table(pyproject_toml: Mapping[str, Any]) -> Mapping[str, Any]:
    target_requires = pyproject_toml.get("build-system", {}).pop("target-requires", [])

    build_system_table = _parse_build_system_table(pyproject_toml)

    build_system_table["target-requires"] = target_requires

    return build_system_table


_builder._parse_build_system_table = parse_xbuild_system_table


###########################################################################
# A ProjectXBuilder that understands how to handle target requirements
############################################################################
class ProjectXBuilder(ProjectBuilder):
    @property
    def build_system_target_requires(self) -> set[str]:
        """The dependencies defined in the ``pyproject.toml``'s
        ``build-system.target-requires`` field.
        """
        return set(self._build_system["target-requires"])

    def get_target_requires_for_build(
        self,
        distribution: Distribution,
        config_settings: ConfigSettings | None = None,
    ) -> set[str]:
        """Return the dependencies defined by the backend in addition to
        :attr:`build_system_requires` for a given distribution.

        :param distribution: Distribution to get the dependencies of
            (``sdist`` or ``wheel``)
        :param config_settings: Config settings for the build backend
        """
        _ctx.log(
            f"Getting target build dependencies for {distribution}...", kind=("step",)
        )
        hook_name = f"get_target_requires_for_build_{distribution}"
        try:
            get_requires = getattr(self._hook, hook_name)

            with self._handle_backend(hook_name):
                return set(get_requires(config_settings))
        except AttributeError:
            # For now, most build backends won't implement
            # get_target_requires_for_build_wheel
            return set()

    def check_target_dependencies(
        self,
        distribution: Distribution,
        config_settings: ConfigSettings | None = None,
    ) -> set[tuple[str, ...]]:
        """
        Return the dependencies which are not satisfied from the combined set of
        :attr:`build_system_target_requires` and
        :meth:`get_target_requires_for_build` for a given distribution.

        :param distribution: Distribution to check (``sdist`` or ``wheel``)
        :param config_settings: Config settings for the build backend
        :returns: Set of variable-length unmet dependency tuples
        """
        dependencies = self.get_target_requires_for_build(distribution, config_settings)
        dependencies |= self.build_system_target_requires

        return {u for d in dependencies for u in check_dependency(d)}
