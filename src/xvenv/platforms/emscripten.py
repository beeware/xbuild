from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

VALID_ARCHES = ["wasm32"]
DEFAULT_ARCH = {
    # Linux architectures
    "aarch64": "wasm32",
    "x86_64": "wasm32",
    # macOS spelling of ARM64
    "arm64": "wasm32",
    # Windows architectures
    "ARM64": "wasm32",
    "AMD64": "wasm32",
}


def build_details_from_sysconfigdata(sysconfigdata):
    # Reconstruct a build_details-alike structure from sysconfigdata.
    build_details = {
        "platform": "emscripten-4.0.12-wasm32",
    }
    return build_details


def extend_context(context, build_details):
    emscripten_version = "4.0.12"
    context["release"] = emscripten_version
    context["platform_version"] = emscripten_version
    context["machine"] = context["arch"]

    context["os_sysname"] = "Emscripten"
    context["os_nodename"] = "emscripten"
    context["os_release"] = emscripten_version
    context["os_version"] = "#1"

    context["sys_extra"] = ""
    context["os_extra"] = ""
    context["platform_extra"] = f"""
    @monkeypatch(platform)
    def libc_ver() -> int:
        return ("emscripten", "{emscripten_version}")
"""


def download_url(version_info: tuple, arch: str) -> str:
    """Compute the python.org download URL for the iOS XCframework build.

    :param version: The `sys.version_info` tuple for the version being
        requested.
    :param arch: The architecture build built. Ignored; this should always be
        wasm32.
    :returns: The download URL.
    """
    raise NotImplementedError(
        "xvenv does not yet know how to download a Python build for emscripten."
    )


def archive_path(path: Path) -> Path:
    """Determine the root of the Python archive based on the location of a
    build_details.json/sysconfigdata.py file."""
    raise NotImplementedError(
        "xvenv does not yet know how to configure a Python build for emscripten."
    )


def config_path(extracted_path: Path, version_info, arch: str):
    raise NotImplementedError(
        "xvenv does not yet know how to configure a Python build for emscripten."
    )


def prepare_env(config) -> dict[str, str]:
    raise NotImplementedError(
        "xvenv does not yet know how to prepare a build environment for emscripten."
    )


def packages_path(work_path):
    return work_path / "site-packages"


def setup_testbed(
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
        if src.is_dir():
            shutil.copytree(src, src_path / src.name, dirs_exist_ok=True)
        else:
            shutil.copy(src, src_path / src.name)


def run_testbed(
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
