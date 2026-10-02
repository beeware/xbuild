from __future__ import annotations

import os
import sys


def host_platform() -> str:
    """The `sys.platform` of the machine actually running this code.

    Inside a cross-platform environment, `sys.platform` reports the *target*
    platform. The generated cross-target module records the original value
    as `sys._host_platform` before patching it.
    """
    return getattr(sys, "_host_platform", sys.platform)


def build_platform_env() -> dict[str, str]:
    """A copy of the current environment with cross-platform patches disabled.

    Use this when running build-platform tools (e.g. `android.py`, or the iOS
    testbed driver) as subprocesses, so they don't inherit the patches of an
    active cross-platform environment.
    """
    return {**os.environ, "XBUILD_ENV": "off"}
