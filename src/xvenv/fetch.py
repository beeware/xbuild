from __future__ import annotations

import os
import platform
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


_HOST_ARCH_FAMILY = {
    "arm64": "arm64",
    "aarch64": "arm64",
    "x86_64": "x86_64",
    "AMD64": "x86_64",
}

_DEFAULT_ARCH = {
    "ios": {
        "arm64": "arm64_iphonesimulator",
        "x86_64": "x86_64_iphonesimulator",
    },
    "android": {
        "arm64": "aarch64",
        "x86_64": "x86_64",
    },
}


def default_arch(platform_name: str) -> str:
    """Compute a "useful default" --arch for a platform, based on the host
    machine's architecture.

    :param platform_name: One of ``"ios"``, ``"android"``, ``"emscripten"``.
    :returns: The default arch string for that platform.
    :raises NotImplementedError: for ``"emscripten"`` (no sensible default
        known yet).
    :raises ValueError: if the host machine architecture is not recognized.
    """
    if platform_name == "emscripten":
        raise NotImplementedError(
            "xvenv does not yet know how to choose a default --arch for emscripten."
        )

    host_machine = platform.machine()
    try:
        arch_family = _HOST_ARCH_FAMILY[host_machine]
    except KeyError:
        raise ValueError(
            f"Don't know a default --arch for {platform_name} on host "
            f"machine architecture {host_machine!r}. Specify --arch "
            "explicitly."
        ) from None

    return _DEFAULT_ARCH[platform_name][arch_family]
