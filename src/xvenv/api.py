from __future__ import annotations

import dataclasses
import venv
from pathlib import Path

from xvenv.convert import convert_venv
from xvenv.fetch import fetch_python, resolve_arch, resolve_cache_dir


@dataclasses.dataclass(frozen=True)
class CrossVenvResult:
    """The result of creating (or reusing) a cross-platform venv.

    :param description: A human-readable description of the resulting
        cross-platform venv, as returned by `convert_venv()` (e.g.
        `"android aarch64-linux-android"`).
    :param archive_dir: The root of the extracted target-platform Python
        archive that was used to build the venv (the same directory
        `xvenv.fetch.fetch_python()` extracted the download into). Contains
        platform-specific resources bundled inside the archive, such as the
        iOS/Android testbed projects.
    """

    description: str
    archive_dir: Path


def create_cross_venv(
    venv_path: Path,
    platform: str,
    arch: str | None,
    cache_dir: Path | None,
    with_pip: bool = True,
) -> CrossVenvResult:
    """Create (if `venv_path` doesn't already exist) and convert a virtual
    environment into a cross-platform venv for `platform`/`arch`,
    downloading (and caching) the target Python build as needed.

    :param venv_path: The path to the root of the venv. Created with
        `venv.create()` if it doesn't already exist; converted in place
        either way.
    :param platform: One of `"ios"`, `"android"`, `"emscripten"`.
    :param arch: The target architecture, or `None` to use a
        host-arch-based default (see `xvenv.fetch.resolve_arch()`).
    :param cache_dir: The directory to use for caching downloaded Python
        builds, or `None` to use the default resolution order (see
        `xvenv.fetch.resolve_cache_dir()`).
    :param with_pip: Whether to install pip when creating the venv. Only
        relevant if `venv_path` doesn't already exist.
    :returns: A `CrossVenvResult` describing the resulting venv and the
        archive directory the target Python build was extracted into.
    :raises ValueError: on an unknown/unsupported arch, or any other error
        `resolve_arch()`, `fetch_python()`, or `convert_venv()` raise.
    :raises NotImplementedError: if `platform`/`arch` isn't supported for
        download yet (e.g. emscripten).
    """
    if not venv_path.exists():
        venv.create(venv_path, with_pip=with_pip)

    resolved_cache_dir = resolve_cache_dir(cache_dir)
    resolved_arch = resolve_arch(platform, arch)

    config_path, is_build_details = fetch_python(
        platform, resolved_arch, resolved_cache_dir
    )

    # archive_dir is the single path component directly under
    # resolved_cache_dir that is an ancestor of config_path.
    relative = config_path.relative_to(resolved_cache_dir)
    archive_dir = resolved_cache_dir / relative.parts[0]

    build_details_path = config_path if is_build_details else None
    sysconfigdata_path = None if is_build_details else config_path

    description = convert_venv(
        venv_path,
        build_details_path=build_details_path,
        sysconfigdata_path=sysconfigdata_path,
    )

    return CrossVenvResult(description=description, archive_dir=archive_dir)


__all__ = ["CrossVenvResult", "create_cross_venv"]
