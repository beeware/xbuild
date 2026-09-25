from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..deps import copy_into


def packages_path(work_path):
    return work_path / "site-packages"


def setup(
    archive_path: Path,
    work_path: Path,
    src_paths: list[Path],
) -> int:
    """Clone the Android testbed, and stage source files into it.

    :param archive_path: The extracted iOS Python archive directory
        (contains a `testbed/` subdirectory with the testbed driver
        script).
    :param work_path: The working directory to clone the testbed into (as
        `work_path / "testbed"`).
    :param src_paths: Paths to copy into the cloned testbed's src directory.
    :raises RuntimeError: if running on macOS
    """
    if sys.platform == "darwin" and "GITHUB_ACTIONS" in os.environ:
        raise RuntimeError(
            "GitHub Actions can't start an Android emulator on a macOS runner."
        )

    src_path = work_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)

    copy_into(archive_path / "android.py", work_path)
    copy_into(archive_path / "testbed", work_path)
    (work_path / "prefix").symlink_to(archive_path / "prefix")
    (work_path / "android-env.sh").symlink_to(archive_path / "android-env.sh")

    for src in src_paths:
        copy_into(src, src_path)


def run(
    work_path: Path,
    args: list[str],
    managed: str | None,
    connected: str | None,
    verbose: int,
    **kwargs,
) -> int:
    """Run the testbed project on an Android emulator/device..

    :param work_path: The working directory to build staging directories
        in (`work_path / "site-packages"`, `work_path / "cwd"`).
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
        str(work_path / "android.py"),
        "test",
        "--site-packages",
        str(packages_path(work_path)),
        "--cwd",
        str(work_path / "src"),
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
