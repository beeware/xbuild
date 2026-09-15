"""Verifies that XBUILD_ENV=off correctly disables xvenv's cross-platform
patching, by running *inside* a cross-venv's own interpreter with that
env var set.

Run via:
    XBUILD_ENV=off <cross-venv>/bin/python -m pytest tests/live/_inner/disabled

Only makes structural assertions (not exact native-value comparisons),
since the exact native sys.platform/sysconfig values depend on whatever
host machine happens to run this test (e.g. "darwin" on macOS CI/dev
machines, "linux" on Linux CI runners).
"""

import sys
import sysconfig


def test_cross_compiling_is_disabled():
    """Cross compilation is not enabled."""
    assert not getattr(sys, "cross_compiling", False)


def test_platform_is_native():
    """The platform isn't a known cross-platform environment"""
    assert sys.platform not in {"ios", "android", "emscripten"}


def test_get_paths_scripts_is_venv_local():
    """The sysconfig paths in the environment point to the venv."""
    # Paths still resolve to the venv itself, not
    # somewhere referencing a target-platform build.
    paths = sysconfig.get_paths()
    assert paths["scripts"].startswith(sys.prefix)
