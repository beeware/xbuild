from __future__ import annotations

import os
from collections.abc import Collection
from contextlib import contextmanager
from pathlib import Path
from typing import Self

from build import _ctx
from build import env as build_env
from build.env import DefaultIsolatedEnv, _PipBackend


###########################################################################
# Patch `build.env._PipBackend` to disable the cross-build environment
# for installs if the install is not for the target.
###########################################################################
@contextmanager
def install_environment(os, for_target):
    """A context manager that temporarily configures the XBUILD_ENV variable.

    :param for_target: If False, disables any active cross-venv by setting
        XBUILD_ENV=off in the environment.
    """
    old_xbuild_env = os.environ.get("XBUILD_ENV", None)
    if not for_target:
        os.environ["XBUILD_ENV"] = "off"

    yield
    if not for_target:
        if old_xbuild_env is None:
            del os.environ["XBUILD_ENV"]
        else:
            os.environ["XBUILD_ENV"] = old_xbuild_env


class _XPipBackend(_PipBackend):
    def install_dependencies(
        self,
        requirements: Collection[str],
        constraints: Collection[str] = (),
        *,
        for_target: bool = True,
        _fresh: bool = False,
    ) -> None:
        with install_environment(os, for_target=for_target):
            super().install_dependencies(requirements, constraints, _fresh=_fresh)


build_env._PipBackend = _XPipBackend


###########################################################################
# An isolated environment manager that creates cross-plaform installs,
# and can handle both build and target dependency installs.
###########################################################################
class XBuildIsolatedEnv(DefaultIsolatedEnv):
    def __init__(self, *, installer, cross_venv):
        if installer == "uv":
            raise RuntimeError("Can't support uv (for now)")

        super().__init__()
        self.cross_venv = cross_venv

    def __enter__(self) -> Self:
        super().__enter__()

        # Make the isolated environment a cross environment. The cross venv
        # configuration has already been resolved, either from explicit
        # arguments, or from the active cross-platform environment.
        self.cross_venv.convert(Path(self._path))

        return self

    def install(self, requirements: Collection[str], for_target=True) -> None:
        """Install packages from PEP 508 requirements in the isolated build environment.

        :param requirements: PEP 508 requirement specification to install
        :param for_target: Should the the cross build environment be active? True by
            default; if False, `XBUILD_ENV=off` will be used to install build platform
            binaries, rather than target platform binaries,
        """
        if not requirements:
            return

        for_loc = "target platform" if for_target else "build platform"
        _ctx.log(
            f"Installing packages for {for_loc} in isolated environment:\n"
            + "\n".join(f"- {r}" for r in sorted(requirements)),
            kind=("step",),
        )
        self._env_backend.install_dependencies(requirements, for_target=for_target)
