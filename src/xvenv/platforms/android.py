from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from xvenv import versions

VALID_ARCHES = ["aarch64", "x86_64"]
DEFAULT_ARCH = {
    # Linux architectures
    "aarch64": "aarch64",
    "x86_64": "x86_64",
    # macOS spelling of ARM64
    "arm64": "aarch64",
    # Windows architectures
    "ARM64": "aarch64",
    "AMD64": "x86_64",
}


def download_url(version_info: tuple, arch: str) -> str:
    """Compute the python.org download URL for the iOS XCframework build.

    :param version: The `sys.version_info` tuple for the version being
        requested.
    :param arch: The architecture build built.
    :returns: The download URL.
    """
    series = versions.series(version_info)
    if version_info[:2] < (3, 13):
        raise ValueError(f"xbuild doesn't support Python {series} on Android")
    elif series == "3.13":
        return (
            "https://repo.maven.apache.org/maven2/com/chaquo/python/python/"
            f"3.13.15/python-3.13.15-{arch}-linux-android.tar.gz"
        )
    else:
        version = versions.version(version_info)
        release = versions.release(version_info)
        return (
            f"https://www.python.org/ftp/python/{release}/"
            f"python-{version}-{arch}-linux-android.tar.gz"
        )


def archive_path(path: Path) -> Path:
    """Determine the root of the Python archive based on the location of a
    build_details.json/sysconfigdata.py file."""
    return path.parents[3]


def config_path(extracted_dir: Path, version_info, arch: str) -> Path:
    """Locate the sysconfig/build-details file inside an extracted Android
    archive.

    :param extracted_dir: The root of the extracted archive.
    :param version_info: A `sys.version_info`-shaped value for the Python
        version the archive contains.
    :param arch: One of the values in `VALID_ARCHES`, e.g. `"aarch64"`.
    :returns: The path to `build-details.json` (Python 3.14+) or the
        legacy `_sysconfigdata__android_*.py` module (Python <3.14).
    """
    py_dir = (
        extracted_dir
        / "prefix"
        / "lib"
        / f"python{version_info.major}.{version_info.minor}"
    )
    if version_info[:2] >= (3, 14):
        return py_dir / "build-details.json"
    return py_dir / f"_sysconfigdata__android_{arch}-linux-android.py"


def build_details_from_sysconfigdata(sysconfigdata):
    # Reconstruct a build_details-alike structure from sysconfigdata.
    arch, _, platform = sysconfigdata["MULTIARCH"].split("-")
    min_api_level = sysconfigdata["ANDROID_API_LEVEL"]
    build_details = {
        "platform": f"{platform}-{min_api_level}-{arch}",
    }
    return build_details


def extend_context(context, build_details):
    # Convert the API level into a release number
    api_level = int(build_details["platform"].split("-")[1])
    if api_level >= 33:
        release = f"{api_level - 20}"
    elif api_level == 32:
        release = "12L"
    elif api_level == 31:
        release = "12"
    elif api_level > 28:
        release = f"{api_level - 19}"
    elif api_level == 27:
        release = "8.1"
    elif api_level == 26:
        release = "8.0"
    elif api_level == 25:
        release = "7.1"
    elif api_level == 24:
        release = "7.0"
    elif api_level == 23:
        release = "6.0"
    elif api_level == 22:
        release = "5.1"
    elif api_level == 21:
        release = "5.0"
    elif api_level == 20:
        release = "4.4W"
    else:
        raise ValueError("xbuild doesn't support API levels lower than 20")

    ######################################################################
    context["os"] = "Android"
    context["release"] = release
    context["platform_version"] = api_level
    context["machine"] = {
        "x86_64": "x86_64",
        "i686": "x86",
        "aarch64": "arm64_v8a",
        "armv7l": "armeabi_v7a",
    }[context["arch"]]

    # The Linux kernel version and release are unlikely to be
    # significant, but return realistic values anyway (from an
    # API level 24 emulator).
    context["os_sysname"] = "Linux"
    context["os_nodename"] = "localhost"
    context["os_release"] = "3.18.91+"
    context["os_version"] = "#1 SMP PREEMPT Tue Jan 9 20:35:43 UTC 2018"

    context["sys_extra"] = f"""

    @monkeypatch(sys)
    def getandroidapilevel() -> int:
        return {api_level}
"""
    context["os_extra"] = ""
    context["platform_extra"] = f"""

    @monkeypatch(platform)
    def android_ver(
        release="",
        api_level=0,
        manufacturer="",
        model="",
        device="",
        is_emulator=False
    ):
        if release == "":
            release = "{release}"
        if api_level == 0:
            api_level = {api_level}
        if manufacturer == "":
            manufacturer = "Google"
        if model == "":
            model = "sdk_gphone64"
        if device == "":
            device = "emu64"

        return platform.AndroidVer(
            release, api_level, manufacturer, model, device, True
        )

"""


def prepare_env(config) -> dict[str, str]:
    """Prepare CC/AR/CXX/etc. environment variables for compiling Android
    native code.

    This runs the archive's own `android.py env` subcommand to establish
    environment overrides and ensure the required NDK is installed.

    :param config: The resolved `xvenv.convert.CrossVenvConfig`.
    :returns: A dict of environment variables (AR, AS, CC, CXX, LD, NM,
        RANLIB, READELF, STRIP, CFLAGS, LDFLAGS, CXXFLAGS, CPU_COUNT,
        and -- if a prefix/ directory exists in the archive --
        PKG_CONFIG/PKG_CONFIG_LIBDIR).
    :raises ValueError: if ANDROID_HOME isn't set, the archive's
        `android.py` can't be found, or `android.py env` exits with an
        error (e.g. a toolchain binary is missing).
    """
    if not os.environ.get("ANDROID_HOME"):
        raise ValueError(
            "ANDROID_HOME environment variable is not set. It must "
            "point at an installed Android SDK."
        )

    android_py = config.archive_path / "android.py"
    if not android_py.is_file():
        raise ValueError(f"Could not find {android_py}")

    try:
        result = subprocess.run(
            [sys.executable, str(android_py), "env"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(f"{android_py} env failed:\n{e.stdout}{e.stderr}") from e

    android_env: dict[str, str] = {}
    for i, token in enumerate(shlex.split(result.stdout)):
        if i % 2 == 0:
            if token != "export":
                raise ValueError(
                    f"Unexpected output from {android_py} env: expected "
                    f"'export', got {token!r}"
                )
        else:
            key, sep, value = token.partition("=")
            if sep != "=":
                raise ValueError(
                    f"Unexpected output from {android_py} env: expected "
                    f"'key=value', got {token!r}"
                )
            android_env[key] = value

    return android_env


def packages_path(work_path):
    return work_path / "site-packages"


def setup_testbed(
    archive_path: Path,
    work_path: Path,
    src_paths: list[Path],
):
    """Clone the Android testbed, and stage source files into it.

    :param archive_path: The extracted Android Python archive directory
        (contains a `testbed/` subdirectory with the testbed driver
        script).
    :param work_path: The working directory to clone the testbed into.
    :param src_paths: Paths to copy into the cloned testbed's src directory.
    :raises RuntimeError: if running on GitHub actions on a macOS runner.
    """
    if sys.platform == "darwin" and "GITHUB_ACTIONS" in os.environ:
        raise RuntimeError(
            "GitHub Actions can't start an Android emulator on a macOS runner."
        )

    src_path = work_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)

    shutil.copy(archive_path / "android.py", work_path / "android.py")
    shutil.copytree(archive_path / "testbed", work_path / "testbed", dirs_exist_ok=True)
    (work_path / "prefix").symlink_to(archive_path / "prefix")
    (work_path / "android-env.sh").symlink_to(archive_path / "android-env.sh")

    for src in src_paths:
        if src.is_dir():
            shutil.copytree(src, src_path / src.name, dirs_exist_ok=True)
        else:
            shutil.copy(src, src_path / src.name)


def run_testbed(
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
