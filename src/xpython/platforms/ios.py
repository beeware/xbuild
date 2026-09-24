from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ..deps import copy_into


def testbed_dir(work_dir):
    return work_dir / "testbed"


def packages_dir(work_dir):
    return testbed_dir(work_dir) / "iOSTestbed" / "app_packages"


def setup(archive_dir: Path, work_dir: Path, src_paths: list[Path]):
    """Clone the iOS testbed, and stage source files into it.

    :param archive_dir: The extracted iOS Python archive directory
        (contains a `testbed/` subdirectory with the testbed driver
        script).
    :param work_dir: The working directory to clone the testbed into (as
        `work_dir / "testbed"`).
    :param src_paths: Paths to copy into the cloned testbed's
        `iOSTestbed/app/` directory.
    """
    testbed_source = archive_dir / "testbed"
    testbed_clone = testbed_dir(work_dir)

    subprocess.run(
        [sys.executable, str(testbed_source), "clone", str(testbed_clone)],
        check=True,
    )
    # Copy sources into the app
    for src in src_paths:
        copy_into(src, testbed_clone / "iOSTestbed" / "app")


def run(
    work_dir: Path,
    args: list[str],
    simulator: str | None,
    verbose: int,
    **kwargs,
) -> int:
    """Run the testbed project inside the iOS Simulator.

    :param work_dir: The working directory to clone the testbed into (as
        `work_dir / "testbed"`).
    :param args: Arguments to pass to the testbed.
    :param simulator: The name of the iOS simulator to use, or `None` to
        use the testbed driver's own default.
    :param verbose: Verbosity level; > 0 forwards `-v` to the driver's
        `run` subcommand.
    :returns: The exit code of the testbed driver's `run` subcommand.
    """
    if args and (args[0] != "-m" or len(args) < 2):
        raise ValueError("iOS requires -m <module> as the first two arguments after --")

    testbed_clone = testbed_dir(work_dir)

    run_command = [sys.executable, str(testbed_clone), "run"]
    if simulator is not None:
        run_command.extend(["--simulator", simulator])
    if verbose > 0:
        run_command.append("-v")

    run_command.extend(["--", *args[1:]])

    result = subprocess.run(run_command, check=False)
    return result.returncode


__all__ = ["run", "setup"]
