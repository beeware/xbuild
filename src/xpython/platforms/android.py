from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _copy_into(src: Path, dst_dir: Path) -> None:
    """Copy `src` (file or directory) into `dst_dir / src.name`."""
    target = dst_dir / src.name
    if src.is_dir():
        shutil.copytree(src, target, dirs_exist_ok=True)
    else:
        shutil.copy(src, target)


def stage_and_run(
    archive_dir: Path,
    work_dir: Path,
    src_paths: list[Path],
    packages_dir: Path,
    forwarded_args: list[str],
    managed: str | None,
    connected: str | None,
    verbose: int,
) -> int:
    """Stage source/package files and run `android.py test -- <forwarded_args>`
    inside an Android emulator/device, using the `android.py` driver
    bundled alongside the downloaded Android Python archive.

    :param archive_dir: The extracted Android Python archive directory
        (contains `android.py` and its own bundled `testbed/` Gradle
        project, used in place -- no separate clone step, unlike iOS).
    :param work_dir: The working directory to build staging directories
        in (`work_dir / "site-packages"`, `work_dir / "cwd"`).
    :param src_paths: Paths to copy into `work_dir / "cwd"`.
    :param packages_dir: A directory whose contents are copied into
        `work_dir / "site-packages"`.
    :param forwarded_args: Arguments to pass verbatim to `android.py
        test`'s own `-- <args>` mechanism (e.g. `["-m", "pytest",
        "tests"]` or `["-c", "print(1)"]`). No validation is applied here
        -- `android.py` itself accepts `-c`/`-m`, or defaults to `-m test`
        if `forwarded_args` is empty.
    :param managed: The name of a Gradle-managed device to use, or `None`.
    :param connected: The serial of an already-connected device to use, or
        `None`. Mutually exclusive with `managed`; if both are `None`,
        defaults to `--managed maxVersion`.
    :param verbose: Verbosity level; > 0 forwards `-v` to `android.py`.
    :returns: The exit code of the `android.py test` subprocess.
    """
    site_packages_dir = work_dir / "site-packages"
    cwd_dir = work_dir / "cwd"
    site_packages_dir.mkdir(parents=True, exist_ok=True)
    cwd_dir.mkdir(parents=True, exist_ok=True)

    for item in packages_dir.iterdir():
        _copy_into(item, site_packages_dir)

    for src in src_paths:
        _copy_into(src, cwd_dir)

    android_driver = archive_dir / "android.py"
    command = [
        str(android_driver),
        "test",
        "--site-packages",
        str(site_packages_dir),
        "--cwd",
        str(cwd_dir),
    ]
    if connected is not None:
        command.extend(["--connected", connected])
    else:
        command.extend(["--managed", managed or "maxVersion"])
    if verbose > 0:
        command.append("-v")
    command.extend(["--", *forwarded_args])

    result = subprocess.run(command, check=False)
    return result.returncode


__all__ = ["stage_and_run"]
