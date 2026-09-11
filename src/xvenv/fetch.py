from __future__ import annotations

import os
import sys
from pathlib import Path

import platformdirs


def resolve_cache_dir(cache_arg: Path | None) -> Path:
    """Resolve the cache directory to use for downloaded Python builds.

    Priority order:

    1. `cache_arg` (typically from the ``--cache`` CLI option), if given.
    2. The ``XBUILD_CACHE`` environment variable, if set.
    3. ``platformdirs.user_cache_dir("xbuild")``.

    The resolved directory is created if it doesn't already exist.

    :param cache_arg: An explicit cache directory, or ``None``.
    :returns: The resolved cache directory.
    """
    if cache_arg is not None:
        cache_dir = Path(cache_arg)
    elif (env_cache := os.environ.get("XBUILD_CACHE")) is not None:
        cache_dir = Path(env_cache)
    else:
        cache_dir = Path(platformdirs.user_cache_dir("xbuild"))

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


_RELEASELEVEL_SUFFIX = {
    "alpha": "a",
    "beta": "b",
    "candidate": "rc",
    "final": "",
}


def python_version_string(version_info=sys.version_info) -> str:
    """Compute the python.org download version string for a version_info tuple.

    :param version_info: A ``sys.version_info``-shaped value (defaults to the
        currently running interpreter's version).
    :returns: e.g. ``"3.14.7"`` for a final release, or ``"3.15.0rc2"`` for a
        release candidate.
    """
    base = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    suffix = _RELEASELEVEL_SUFFIX[version_info.releaselevel]
    if suffix:
        return f"{base}{suffix}{version_info.serial}"
    return base
