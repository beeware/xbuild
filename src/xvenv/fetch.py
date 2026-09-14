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

    1. `cache_arg` (typically from the `--cache` CLI option), if given.
    2. The `XBUILD_CACHE` environment variable, if set.
    3. `platformdirs.user_cache_dir("xbuild")`.

    The resolved directory is created if it doesn't already exist.

    :param cache_arg: An explicit cache directory, or `None`.
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


def resolve_arch(platform_name: str, arch: str | None) -> str:
    """Resolve the architecture for the build, resolving a "useful default"
    based on the host machine's architecture if an architecture wasn't specified

    :param platform_name: One of `"ios"`, `"android"`, `"emscripten"`.
    :returns: The resolved arch string for that platform.
    :raises ValueError: if the host machine architecture is not recognized.
    """
    platform_module = import_module(f"xvenv.platforms.{platform_name}")

    if arch is not None:
        if arch not in platform_module.VALID_ARCHES:
            raise ValueError(
                f"{arch!r} is not a valid --arch for {platform_name}. "
                f"Valid values are: {', '.join(platform_module.VALID_ARCHES)}"
            )
        else:
            return arch

    host_machine = platform.machine()
    try:
        return platform_module.DEFAULT_ARCH[host_machine]
    except KeyError:
        raise ValueError(
            f"Don't know a default --arch for {platform_name} on host "
            f"machine architecture {host_machine!r}. Specify --arch "
            "explicitly."
        ) from None


def _current_version_info():
    """Indirection so tests can monkeypatch/mock the interpreter version
    without needing to patch the sys module itself."""
    return sys.version_info


def fetch_python(platform_name: str, arch: str, cache_dir: Path) -> tuple[Path, bool]:
    """Download (if not already cached) and locate the sysconfig/build-details
    file for a target platform/arch's Python build.

    :param platform_name: One of `"ios"`, `"android"`, `"emscripten"`.
    :param arch: The target architecture.
    :param cache_dir: The (already-resolved, already-existing) cache
        directory to use — see :func:`resolve_cache_dir`.
    :returns: A tuple of `(config_path, is_build_details)`, where
        `is_build_details` is `True` if `config_path` is a
        `build-details.json` file, `False` if it's a legacy
        `_sysconfigdata__*.py` module.
    :raises ValueError: if `arch` is not a valid arch for `platform_name`.
    """
    platform_module = import_module(f"xvenv.platforms.{platform_name}")
    version_info = _current_version_info()
    url = platform_module.download_url(version_info, arch)

    archive_name = url.rsplit("/", 1)[-1]
    extracted_name = archive_name[: -len(".tar.gz")]
    extracted_dir = cache_dir / extracted_name

    if not extracted_dir.is_dir():
        archive_path = cache_dir / archive_name
        if archive_path.is_file():
            print(f"Cached {archive_name} exists.")
        else:
            print(f"Downloading {archive_name}...", end="", flush=True)
            try:
                urllib.request.urlretrieve(url, archive_path)
                print(" done.")
            except OSError as e:
                raise ValueError(f"Failed to download {url}: {e}") from e

        # NOTE: if extraction fails partway (disk full, corrupt archive),
        # extracted_dir already exists and will be treated as a valid cache
        # hit on retry. No rollback/cleanup on partial failure -- delete the
        # cache directory manually to retry a failed download.
        print(f"Extracting {archive_name}...", end="", flush=True)
        extracted_dir.mkdir()
        with tarfile.open(archive_path) as tar:
            tar.extractall(extracted_dir, filter="data")
        print(" done.")

    config_file = platform_module.config_path(extracted_dir, version_info, arch)
    return config_file, config_file.name == "build-details.json"
