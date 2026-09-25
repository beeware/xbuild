from __future__ import annotations

import subprocess
from pathlib import Path

from ..deps import copy_into


def packages_path(work_path):
    return work_path / "site-packages"


def setup(
    archive_path: Path,
    work_path: Path,
    src_paths: list[Path],
) -> int:
    """Clone the Emscripten testbed, and stage source files into it.

    :param archive_path: The extracted Emscripten Python archive directory
    :param work_path: The working directory to clone the testbed into.
    :param src_paths: Paths to copy into the cloned testbed's src directory.
    """
    raise NotImplementedError(
        "xpython does not yet know how to run emscripten projects."
    )

    src_path = work_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)

    for src in src_paths:
        copy_into(src, src_path)


def run(
    work_path: Path,
    args: list[str],
    verbose: int,
    **kwargs,
) -> int:
    """Run the testbed project in an Emscripten environment.

    :param work_path: The working directory to build staging directories
        in (`work_path / "site-packages"`, `work_path / "cwd"`).
    :param args: Arguments to pass to the testbed process. Accepts any
        argument list starting with `-c`/`-m`; defaults to `-m test`
        if `args` is empty.
    :param verbose: Verbosity level; > 0 forwards `-v` to `android.py`.
    :returns: The exit code of the subprocess.
    """
    raise NotImplementedError(
        "xpython does not yet know how to run emscripten projects."
    )

    command = []
    if verbose > 0:
        command.append("-v")

    result = subprocess.run(command, check=False)
    return result.returncode


__all__ = ["run", "setup"]
