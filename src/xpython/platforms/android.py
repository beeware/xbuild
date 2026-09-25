from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..deps import copy_into


def packages_dir(work_dir):
    return work_dir / "site-packages"


def setup(
    archive_dir: Path,
    work_dir: Path,
    src_paths: list[Path],
) -> int:
    """Clone the Android testbed, and stage source files into it.

    :param archive_dir: The extracted iOS Python archive directory
        (contains a `testbed/` subdirectory with the testbed driver
        script).
    :param work_dir: The working directory to clone the testbed into (as
        `work_dir / "testbed"`).
    :param src_paths: Paths to copy into the cloned testbed's src directory.
    :raises RuntimeError: if running on macOS
    """
    if sys.platform == "darwin" and "GITHUB_ACTIONS" in os.environ:
        raise RuntimeError(
            "GitHub Actions can't start an Android emulator on a macOS runner."
        )

    src_dir = work_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    copy_into(archive_dir / "android.py", work_dir)
    copy_into(archive_dir / "testbed", work_dir)
    (work_dir / "prefix").symlink_to(archive_dir / "prefix")
    (work_dir / "android-env.sh").symlink_to(archive_dir / "android-env.sh")

    for src in src_paths:
        copy_into(src, src_dir)


def run(
    work_dir: Path,
    args: list[str],
    managed: str | None,
    connected: str | None,
    verbose: int,
    **kwargs,
) -> int:
    """Run the testbed project on an Android emulator/device..

    :param work_dir: The working directory to build staging directories
        in (`work_dir / "site-packages"`, `work_dir / "cwd"`).
    :param args: Arguments to pass to the testbed process. Accepts any
        argument list starting with `-c`/`-m`; defaults to `-m test`
        if `args` is empty.
    :param managed: The name of a Gradle-managed device to use, or `None`.
    :param connected: The serial of an already-connected device to use, or
        `None`. Mutually exclusive with `managed`; if both are `None`,
        defaults to `--managed maxVersion`.
    :param verbose: Verbosity level; > 0 forwards `-v` to `android.py`.
    :returns: The exit code of the `android.py test` subprocess.
    """
    if "GITHUB_ACTIONS" in os.environ and sys.platform == "linux":
        # Enable emulator hardware acceleration on GitHub Actions.
        # (https://github.blog/changelog/2024-04-02-github-actions-hardware-accelerated-android-virtualization-now-available/).
        print("Enabling GitHub Actions hardware acceleration...")
        subprocess.run(
            ["sudo", "tee", "/etc/udev/rules.d/99-kvm4all.rules"],
            input=(
                'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"\n'
            ),
            text=True,
            check=True,
        )
        subprocess.run(
            ["sudo", "udevadm", "control", "--reload-rules"],
            check=True,
        )
        subprocess.run(
            ["sudo", "udevadm", "trigger", "--name-match=kvm"],
            check=True,
        )

    command = [
        str(work_dir / "android.py"),
        "test",
        "--site-packages",
        str(packages_dir(work_dir)),
        "--cwd",
        str(work_dir / "src"),
    ]
    if connected is not None:
        command.extend(["--connected", connected])
    else:
        command.extend(["--managed", managed or "maxVersion"])
    if verbose > 0:
        command.append("-v")
    command.extend(["--", *args])

    result = subprocess.run(command, check=False)
    return result.returncode


__all__ = ["run", "setup"]
