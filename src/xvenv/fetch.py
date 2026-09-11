from __future__ import annotations

import os
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
