from __future__ import annotations

import os
import sys

# A user may set this environment variable to the directory where a platform's
# `prepare_env()` should create its compiler wrapper scripts (see
# `xvenv.platforms.emscripten`). The directory is left in place afterwards,
# which helps with reproducing problems. If it isn't set, a temporary directory
# is used.
COMPILER_WRAPPER_DIR_VAR = "XBUILD_COMPILER_WRAPPER_DIR"

# A platform's `prepare_env()` sets this environment variable to the compiler
# wrapper directory that is actually in use for the current build. xbuild
# ensures that directory stays at the front of PATH when invoking build
# backends, even though the isolated build environment's own `bin` directory
# is also prepended to PATH. This is deliberately distinct from
# `COMPILER_WRAPPER_DIR_VAR`: a stale user-level export of that variable must
# not cause wrappers to be injected into builds for other platforms.
ACTIVE_COMPILER_WRAPPER_DIR_VAR = "XBUILD_ACTIVE_COMPILER_WRAPPER_DIR"

# When a compiler wrapper directory is in use, xbuild sets this environment
# variable to the `bin` directory of the environment where build dependencies
# (cmake, meson, ninja, ...) have been installed, so the wrappers can find them.
#
# This value is duplicated in `xvenv.platforms.emscripten.pywasmcross`, which
# must remain importable without xvenv; a test keeps the two in sync.
BUILD_ENV_SCRIPTS_DIR_VAR = "XBUILD_BUILD_ENV_SCRIPTS_DIR"


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
