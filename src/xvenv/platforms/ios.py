from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from xvenv import versions
from xvenv.platforms import build_platform_env, host_platform

VALID_ARCHES = ["arm64-iphonesimulator", "x86_64-iphonesimulator", "arm64-iphoneos"]
DEFAULT_ARCH = {
    "arm64": "arm64-iphonesimulator",
    "x86_64": "x86_64-iphonesimulator",
}


def download_url(version_info: tuple, arch: str) -> str:
    """Compute the python.org download URL for the iOS XCframework build.

    :param version: The `sys.version_info` tuple for the version being
        requested.
    :param arch: The architecture build built. Ignored; the single XCframework
        download includes all architectures.
    :returns: The download URL.
    """
    version = versions.version(version_info)
    release = versions.release(version_info)
    series = versions.series(version_info)
    if version_info[:2] < (3, 11):
        raise ValueError(f"xbuild doesn't support Python {series} on iOS")
    elif version_info[:2] < (3, 15):
        build = {
            "3.11": "b11",
            "3.12": "b11",
            "3.13": "b16",
            "3.14": "b12",
        }[series]
        return (
            "https://github.com/beeware/Python-Apple-support/releases/download/"
            f"{series}-{build}/Python-{series}-iOS-support.{build}.tar.gz"
        )
    return (
        f"https://www.python.org/ftp/python/{release}/"
        f"python-{version}-iOS-XCframework.tar.gz"
    )


def archive_path(path: Path) -> Path:
    """Determine the root of the Python archive based on the location of a
    build_details.json/sysconfigdata.py file."""
    return path.parents[4]


def config_path(extracted_dir: Path, version_info: tuple, arch: str) -> Path:
    """Locate the sysconfig/build-details file inside an extracted iOS
    XCframework archive.

    :param extracted_dir: The root of the extracted archive.
    :param version_info: A `sys.version_info`-shaped value for the Python
        version the archive contains.
    :param arch: One of the values in `VALID_ARCHES`, e.g.
        `"arm64_iphonesimulator"`.
    :returns: The path to `build-details.json` (Python 3.14+) or the
        legacy `_sysconfigdata__ios_*.py` module (Python <3.14).
    """
    cpu, sdk = arch.rsplit("-", 1)
    if sdk == "iphonesimulator":
        slice_dir = "ios-arm64_x86_64-simulator"
    else:
        slice_dir = "ios-arm64"
    py_dir = (
        extracted_dir
        / "Python.xcframework"
        / slice_dir
        / f"lib-{cpu}"
        / f"python{version_info.major}.{version_info.minor}"
    )
    if version_info[:2] >= (3, 14):
        return py_dir / "build-details.json"
    return py_dir / f"_sysconfigdata__ios_{cpu}-{sdk}.py"


def build_details_from_sysconfigdata(sysconfigdata):
    # Reconstruct a build_details-alike structure from sysconfigdata.
    platform = sysconfigdata["MACHDEP"]
    multiarch = sysconfigdata["MULTIARCH"]
    ios_target = sysconfigdata["IPHONEOS_DEPLOYMENT_TARGET"]
    build_details = {
        "platform": f"{platform}-{ios_target}-{multiarch}",
    }
    return build_details


def extend_context(context, build_details):
    release = build_details["platform"].split("-")[1]
    is_simulator = context["sdk"] == "iphonesimulator"

    ######################################################################
    context["os"] = "iOS"
    context["release"] = release
    context["platform_version"] = release
    context["machine"] = context["multiarch"]

    # The Darwin kernel version and release are unlikely to be
    # significant, but return realistic values anyway (from an
    # iPhone simulator).
    context["os_sysname"] = "Darwin"
    context["os_nodename"] = "buildmachine.local"
    context["os_release"] = "24.4.0"
    context["os_version"] = (
        "Darwin Kernel Version 24.4.0: Fri Apr 11 18:33:47 PDT 2025; "
        "root:xnu-11417.101.15~117/RELEASE_ARM64_T6000"
    )

    context["sys_extra"] = ""
    context["os_extra"] = ""
    context["platform_extra"] = f"""
    @monkeypatch(platform)
    def ios_ver(system="", release="", model="", is_simulator=False):
        if system == "":
            system = "iOS"
        if release == "":
            release = "{release}"
        if model == "":
            model = "{context["sdk"]}"

        return platform.IOSVersionInfo(system, release, model, {is_simulator})
"""


def prepare_env(config) -> dict[str, str]:
    """Prepare PATH so that target-platform clang/ar/strip shims are used
    for compilation, and no build-machine-native tools leak in.

    :param config: The resolved `xvenv.convert.CrossVenvConfig`.
    :returns: A dict containing a fully-replaced PATH.
    :raises ValueError: if not running on macOS, or Xcode command-line
        tools are not installed/selected.
    """
    if host_platform() != "darwin":
        raise ValueError("Building for iOS requires macOS.")
    if shutil.which("xcrun") is None:
        raise ValueError(
            "Xcode command-line tools are required to build for iOS. "
            "Run `xcode-select --install`, or select an Xcode install "
            "with `sudo xcode-select -s /Applications/Xcode.app`."
        )

    _cpu, sdk = config.arch.rsplit("-", 1)
    slice_dir = (
        "ios-arm64_x86_64-simulator" if sdk == "iphonesimulator" else "ios-arm64"
    )
    slice_bin_dir = config.archive_path / "Python.xcframework" / slice_dir / "bin"

    return {
        "PATH": os.pathsep.join(
            [
                str(Path(sys.executable).parent),
                str(slice_bin_dir),
                "/usr/bin",
                "/bin",
                "/usr/sbin",
                "/sbin",
                "/Library/Apple/usr/bin",
            ]
        ),
    }


def testbed_path(work_path):
    return work_path / "testbed"


def packages_path(work_path):
    return testbed_path(work_path) / "iOSTestbed" / "app_packages"


def setup_testbed(archive_path: Path, work_path: Path, src_paths: list[Path]):
    """Clone the iOS testbed, and stage source files into it.

    :param archive_path: The extracted iOS Python archive directory
        (contains a `testbed/` subdirectory with the testbed driver
        script).
    :param work_path: The working directory to clone the testbed into.
    :param src_paths: Paths to copy into the cloned testbed's
        `iOSTestbed/app/` directory.
    :raises RuntimeError: If not on a macOS machine.
    """
    if host_platform() != "darwin":
        raise RuntimeError("Can't run an iOS project on non-macOS hardware.")

    testbed_source = archive_path / "testbed"
    testbed_clone = testbed_path(work_path)
    target = testbed_clone / "iOSTestbed" / "app"

    subprocess.run(
        [sys.executable, str(testbed_source), "clone", str(testbed_clone)],
        check=True,
        env=build_platform_env(),
    )
    # Copy sources into the app
    for src in src_paths:
        if src.is_dir():
            shutil.copytree(src, target / src.name, dirs_exist_ok=True)
        else:
            shutil.copy(src, target / src.name)


def run_testbed(
    work_path: Path,
    args: list[str],
    simulator: str | None,
    verbose: int,
    **kwargs,
) -> int:
    """Run the testbed project inside the iOS Simulator.

    :param work_path: The working directory to clone the testbed into (as
        `work_path / "testbed"`).
    :param args: Arguments to pass to the testbed.
    :param simulator: The name of the iOS simulator to use, or `None` to
        use the testbed driver's own default.
    :param verbose: Verbosity level; > 0 forwards `-v` to the driver's
        `run` subcommand.
    :returns: The exit code of the testbed driver's `run` subcommand.
    """
    if args and (args[0] != "-m" or len(args) < 2):
        raise ValueError("iOS requires -m <module> as the first two arguments after --")

    testbed_clone = testbed_path(work_path)

    run_command = [sys.executable, str(testbed_clone), "run"]
    if simulator is not None:
        run_command.extend(["--simulator", simulator])
    if verbose > 0:
        run_command.append("-v")

    run_command.extend(["--", *args[1:]])

    result = subprocess.run(run_command, check=False, env=build_platform_env())
    return result.returncode
