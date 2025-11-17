from __future__ import annotations

import os
import shutil
import sys
import sysconfig
from collections.abc import Collection
from contextlib import contextmanager
from pathlib import Path

from build import _ctx
from build import env as build_env
from build.env import DefaultIsolatedEnv, _PipBackend

from xvenv.convert import convert_venv


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
    def install_requirements(
        self,
        requirements: Collection[str],
        for_target: bool = True,
    ) -> None:
        with install_environment(os, for_target=for_target):
            super().install_requirements(requirements)


build_env._PipBackend = _XPipBackend


###########################################################################
# An isolated environment manager that creates cross-plaform installs,
# and can handle both build and target dependency installs.
###########################################################################
class XBuildIsolatedEnv(DefaultIsolatedEnv):
    def __init__(self, *, installer, build_details_path, sysconfigdata_path):
        if installer == "uv":
            raise RuntimeError("Can't support uv (for now)")

        super().__init__()
        self.build_details_path = build_details_path
        self.sysconfigdata_path = sysconfigdata_path

    def __enter__(self) -> XBuildIsolatedEnv:
        super().__enter__()

        # If we're not in a cross-compiling environment, the isolated environment
        # that we create must become a cross-compiling environment. Otherwise,
        # transfer the currently active cross-compilation environment to the
        # isolated environment.
        if not getattr(sys, "cross_compiling", False):
            # We're in a local environment.
            # Make the isolated environment a cross environment.
            if self.build_details_path is None and self.sysconfigdata_path is None:
                raise RuntimeError(
                    "Must specify the location of target platform build_details.json "
                    "with --build-details, or sysconfigdata with --sysconfig"
                )

            convert_venv(
                Path(self._path),
                build_details_path=self.build_details_path,
                sysconfigdata_path=self.sysconfigdata_path,
            )
        else:
            # We're already in a cross environment.
            # Copy any _cross_*.pth or _cross_*.py file, plus the cross-platform
            # sysconfig data to the new environment.
            data_name = sysconfig._get_sysconfigdata_name()
            if sys.version_info < (3, 14):
                vars_files = []
            else:
                vars_files = [sysconfig._get_json_data_name()]

            multiarch = sys.implementation._multiarch.replace("-", "_")
            SRC_SITE_PACKAGES = Path(sysconfig.get_path("platlib"))
            for filename in [
                "_cross_venv.pth",
                f"_cross_{sys.platform}_{multiarch}.py",
                f"{data_name}.py",
            ] + vars_files:
                src = SRC_SITE_PACKAGES / filename
                target = Path(self._path) / src.relative_to(
                    SRC_SITE_PACKAGES.parent.parent.parent
                )
                if not target.exists():
                    shutil.copy(src, target)

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
            + "\n".join(f"- {r}" for r in sorted(requirements))
        )
        self._env_backend.install_requirements(requirements, for_target=for_target)
