from __future__ import annotations

import shutil
import subprocess
import sys
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
    module: str,
    module_args: list[str],
    simulator: str | None,
    verbose: int,
) -> int:
    """Clone the iOS testbed, stage source/package files into it, and run
    `-m <module> <module_args>` inside the iOS Simulator.

    :param archive_dir: The extracted iOS Python archive directory
        (contains a `testbed/` subdirectory with the testbed driver
        script).
    :param work_dir: The working directory to clone the testbed into (as
        `work_dir / "testbed"`).
    :param src_paths: Paths to copy into the cloned testbed's
        `iOSTestbed/app/` directory.
    :param packages_dir: A directory whose contents are copied into the
        cloned testbed's `iOSTestbed/app_packages/` directory.
    :param module: The module to run (as `python -m module` would).
    :param module_args: Arguments to pass to the module.
    :param simulator: The name of the iOS simulator to use, or `None` to
        use the testbed driver's own default.
    :param verbose: Verbosity level; > 0 forwards `-v` to the driver's
        `run` subcommand.
    :returns: The exit code of the testbed driver's `run` subcommand.
    """
    testbed_source = archive_dir / "testbed"
    testbed_clone = work_dir / "testbed"

    subprocess.run(
        [sys.executable, str(testbed_source), "clone", str(testbed_clone)],
        check=True,
    )

    app_dir = testbed_clone / "iOSTestbed" / "app"
    app_packages_dir = testbed_clone / "iOSTestbed" / "app_packages"

    for src in src_paths:
        _copy_into(src, app_dir)

    for item in packages_dir.iterdir():
        _copy_into(item, app_packages_dir)

    run_command = [sys.executable, str(testbed_clone), "run"]
    if simulator is not None:
        run_command.extend(["--simulator", simulator])
    if verbose > 0:
        run_command.append("-v")
    run_command.extend(["--", module, *module_args])

    result = subprocess.run(run_command, check=False)
    return result.returncode


__all__ = ["stage_and_run"]
