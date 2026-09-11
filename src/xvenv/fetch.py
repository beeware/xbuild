from __future__ import annotations

import os
import platform
import sys
import tarfile
import urllib.request
from importlib import import_module
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


def _current_version_info():
    """Indirection so tests can monkeypatch/mock the interpreter version
    without needing to patch the sys module itself."""
    return sys.version_info


def fetch_python(
    platform_name: str, arch: str | None, cache_dir: Path
) -> tuple[Path, bool]:
    """Download (if not already cached) and locate the sysconfig/build-details
    file for a target platform/arch's Python build.

    :param platform_name: One of ``"ios"``, ``"android"``, ``"emscripten"``.
    :param arch: The target architecture, or ``None`` to use a host-arch-aware
        default (see :func:`default_arch`).
    :param cache_dir: The (already-resolved, already-existing) cache
        directory to use — see :func:`resolve_cache_dir`.
    :returns: A tuple of ``(config_path, is_build_details)``, where
        ``is_build_details`` is ``True`` if ``config_path`` is a
        ``build-details.json`` file, ``False`` if it's a legacy
        ``_sysconfigdata__*.py`` module.
    :raises ValueError: if `arch` is not a valid arch for `platform_name`.
    """
    platform_module = import_module(f"xvenv.platforms.{platform_name}")

    if arch is None:
        arch = default_arch(platform_name)
    elif arch not in platform_module.VALID_ARCHES:
        raise ValueError(
            f"{arch!r} is not a valid --arch for {platform_name}. "
            f"Valid values are: {', '.join(platform_module.VALID_ARCHES)}"
        )

    version_info = _current_version_info()
    version = python_version_string(version_info)

    if platform_name == "android":
        url = platform_module.download_url(version, arch, version_info)
    else:
        url = platform_module.download_url(version, version_info)

    archive_name = url.rsplit("/", 1)[-1]
    if archive_name.endswith(".tar.gz"):
        extracted_name = archive_name[: -len(".tar.gz")]
    else:
        extracted_name = archive_name
    extracted_dir = cache_dir / extracted_name

    if not extracted_dir.is_dir():
        archive_path = cache_dir / archive_name
        urllib.request.urlretrieve(url, archive_path)
        extracted_dir.mkdir()
        with tarfile.open(archive_path) as tar:
            tar.extractall(extracted_dir, filter="data")

    config_file = platform_module.config_path(extracted_dir, version_info, arch)
    return config_file, config_file.name == "build-details.json"
