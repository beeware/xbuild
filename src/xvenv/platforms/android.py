from __future__ import annotations

import os
import pprint
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from filelock import FileLock

import xpython
from xvenv import versions
from xvenv.fetch import download, download_archive, parse_sysconfigdata
from xvenv.platforms import build_platform_env, host_platform

# The testbed (and its android.py driver) is copied from CPython, and is used
# regardless of the Python version being targeted.
TESTBED_RESOURCES = Path(xpython.__file__).parent / "resources" / "android"

VALID_ARCHES = {
    "aarch64": "aarch64-linux-android",
    "x86_64": "x86_64-linux-android",
}
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


# Python 3.11 and 3.12 don't have official Android builds. Chaquopy publishes
# builds of these versions; but rather than a single archive, each build is a
# set of zip files, which must be assembled into the same layout as an official
# Android release package. Each Chaquopy build is identified by the Python
# version, plus a Chaquopy build number.
CHAQUOPY_BUILDS = {
    "3.11": "3.11.17-0",
    "3.12": "3.12.15-0",
}

# The Android ABI name for each multi-architecture.
ANDROID_ABIS = {
    "aarch64-linux-android": "arm64-v8a",
    "x86_64-linux-android": "x86_64",
}

# The canonical GNU host type for each multi-architecture, as reported by the
# sysconfigdata of official Android builds.
HOST_GNU_TYPES = {
    "aarch64-linux-android": "aarch64-unknown-linux-android",
    "x86_64-linux-android": "x86_64-pc-linux-android",
}


def _chaquopy_url(series: str, classifier: str) -> str:
    """Compute the download URL for one of the zip files of a Chaquopy build.

    :param series: The Python version series (e.g., 3.12).
    :param classifier: The zip file to download: an Android ABI name for the
        binary components, or `stdlib` for the standard library.
    :returns: The download URL.
    """
    build = CHAQUOPY_BUILDS[series]
    return (
        "https://repo.maven.apache.org/maven2/com/chaquo/python/target/"
        f"{build}/target-{build}-{classifier}.zip"
    )


def download_url(version_info: tuple, multiarch: str) -> str:
    """Compute the download URL for the Android build.

    For Python 3.11 and 3.12, this is the URL of the binary components of the
    Chaquopy build; the standard library is a separate download.

    :param version: The `sys.version_info` tuple for the version being
        requested.
    :param multiarch: The mulit-architecture being requested.
    :returns: The download URL.
    """
    series = versions.series(version_info)
    if version_info[:2] < (3, 11):
        raise ValueError(f"xbuild doesn't support Python {series} on Android")
    elif series in CHAQUOPY_BUILDS:
        return _chaquopy_url(series, ANDROID_ABIS[multiarch])
    elif series == "3.13":
        return (
            "https://repo.maven.apache.org/maven2/com/chaquo/python/python/"
            f"3.13.15/python-3.13.15-{multiarch}.tar.gz"
        )
    else:
        version = versions.version(version_info)
        release = versions.release(version_info)
        return (
            f"https://www.python.org/ftp/python/{release}/"
            f"python-{version}-{multiarch}.tar.gz"
        )


def fetch_archive(version_info: tuple, multiarch: str, cache_path: Path) -> Path:
    """Download (if not already cached) and extract the Android Python build.

    For Python 3.11 and 3.12, the Chaquopy build is downloaded, and assembled
    into the layout of an official Android release package.

    :param version_info: The `sys.version_info` tuple for the version being
        requested.
    :param multiarch: The multi-architecture being requested.
    :param cache_path: The cache directory to use.
    :returns: The path of the extracted archive.
    """
    series = versions.series(version_info)
    if series not in CHAQUOPY_BUILDS:
        return download_archive(download_url(version_info, multiarch), cache_path)

    extracted_path = cache_path / f"chaquopy-{CHAQUOPY_BUILDS[series]}-{multiarch}"
    with FileLock(str(extracted_path) + ".lock"):
        if not extracted_path.is_dir():
            abi_zip = download(download_url(version_info, multiarch), cache_path)
            stdlib_zip = download(_chaquopy_url(series, "stdlib"), cache_path)

            print(f"Assembling {extracted_path.name}...", end="", flush=True)
            # Assemble the archive in a temporary location, so that a failure
            # doesn't leave a partial archive in the cache.
            with tempfile.TemporaryDirectory(dir=cache_path) as tmp:
                staging_path = Path(tmp) / extracted_path.name
                assemble_chaquopy_archive(
                    staging_path,
                    abi_zip=abi_zip,
                    stdlib_zip=stdlib_zip,
                    series=series,
                    multiarch=multiarch,
                )
                staging_path.rename(extracted_path)
            print(" done.")

    return extracted_path


def assemble_chaquopy_archive(
    path: Path,
    abi_zip: Path,
    stdlib_zip: Path,
    series: str,
    multiarch: str,
) -> None:
    """Assemble the zip files of a Chaquopy build into the layout of an
    official Android release package.

    :param path: The directory to create, containing the assembled archive.
    :param abi_zip: The zip file of binary components for `multiarch`.
    :param stdlib_zip: The zip file of the standard library.
    :param series: The Python version series (e.g., 3.12).
    :param multiarch: One of the multiarch values from `VALID_ARCHES`,
        e.g. `"aarch64-linux-android"`.
    """
    abi = ANDROID_ABIS[multiarch]
    prefix_path = path / "prefix"
    stdlib_path = prefix_path / "lib" / f"python{series}"

    with zipfile.ZipFile(stdlib_zip) as zf:
        zf.extractall(stdlib_path)

    # The ABI zip contains the headers in include/, shared libraries in
    # jniLibs/<abi>/, and extension modules in lib-dynload/<abi>/. Shared
    # libraries belong in lib/, and extension modules in the standard library.
    with zipfile.ZipFile(abi_zip) as zf:
        zf.extractall(prefix_path)
    for library in (prefix_path / "jniLibs" / abi).iterdir():
        library.rename(prefix_path / "lib" / library.name)
    (prefix_path / "lib-dynload" / abi).rename(stdlib_path / "lib-dynload")
    shutil.rmtree(prefix_path / "jniLibs")
    shutil.rmtree(prefix_path / "lib-dynload")

    # Generate the sysconfigdata module that an official build would provide.
    build_time_vars = parse_sysconfigdata(
        stdlib_path / "_sysconfigdata__linux_.py"
    ).build_time_vars
    with (stdlib_path / f"_sysconfigdata__android_{multiarch}.py").open(
        "w", encoding="utf-8"
    ) as f:
        f.write("# Generated by xvenv from Chaquopy's _sysconfigdata__linux_.py\n")
        f.write("build_time_vars = ")
        pprint.pprint(
            android_sysconfigdata(build_time_vars, multiarch), stream=f, compact=True
        )

    # Add the build tools of an official release package, using the API level
    # of the Chaquopy build. The script is sourced by bash, so it must have
    # Unix line endings on every platform.
    env_script, count = re.subn(
        r"ANDROID_API_LEVEL:=\d+",
        f"ANDROID_API_LEVEL:={build_time_vars['ANDROID_API_LEVEL']}",
        (TESTBED_RESOURCES / "android-env.sh").read_text(encoding="utf-8"),
    )
    if count != 1:
        raise ValueError("Unable to set the API level in android-env.sh")
    (path / "android-env.sh").write_text(env_script, encoding="utf-8", newline="\n")
    shutil.copy(TESTBED_RESOURCES / "android.py", path / "android.py")


def android_sysconfigdata(build_time_vars: dict, multiarch: str) -> dict:
    """Convert the sysconfig data of a Chaquopy build into the form provided by
    official Android builds.

    Before Python 3.13, `sys.platform` was `linux` on Android, so Chaquopy's
    builds provide a `_sysconfigdata__linux_` module that doesn't identify the
    architecture. This module is shared by all architectures, so it describes
    whichever architecture it was generated on.

    :param build_time_vars: The build time variables of the Chaquopy build.
    :param multiarch: One of the multiarch values from `VALID_ARCHES`,
        e.g. `"aarch64-linux-android"`.
    :returns: The build time variables for `multiarch`.
    """
    build_arch = build_time_vars["HOST_GNU_TYPE"].split("-")[0]
    build_triplet = f"{build_arch}-linux-android"

    android_vars = {
        key: (
            value.replace(build_triplet, multiarch) if isinstance(value, str) else value
        )
        for key, value in build_time_vars.items()
    }
    android_vars["MULTIARCH"] = multiarch
    android_vars["HOST_GNU_TYPE"] = HOST_GNU_TYPES[multiarch]
    return android_vars


def archive_path(path: Path) -> Path:
    """Determine the root of the Python archive based on the location of a
    build_details.json/sysconfigdata.py file."""
    return path.parents[3]


def config_path(extracted_dir: Path, version_info, multiarch: str) -> Path:
    """Locate the sysconfig/build-details file inside an extracted Android
    archive.

    :param extracted_dir: The root of the extracted archive.
    :param version_info: A `sys.version_info`-shaped value for the Python
        version the archive contains.
    :param multiarch: One of the multiarch values from `VALID_ARCHES`,
        e.g. `"aarch64-linux-android"`.
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
    return py_dir / f"_sysconfigdata__android_{multiarch}.py"


def prefix_path(config_data_path: Path) -> Path:
    return config_data_path.parents[2]


def patch_sysconfig(sysconfigvars: dict, prefix: Path) -> dict:
    """Remove LDLIBRARY from the sysconfig vars.

    At runtime, ctypes on Android uses `sysconfig.get_config_var("LDLIBRARY")`
    to find libPython; this fails in a cross-environment. Removing the LDLIBRARY
    key causes ctypes to fall back to `ctypes.DLL(None)`, which is the default
    behavior on desktop platforms anyway.
    """
    sysconfigvars.pop("LDLIBRARY")

    return sysconfigvars


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

    context["pre_patch_extra"] = ""
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
            env=build_platform_env(),
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


def post_convert(venv_path: Path, config) -> None:
    """No post-conversion modifications required."""


def packages_path(work_path):
    return work_path / "site-packages"


def setup_testbed(
    archive_path: Path,
    work_path: Path,
    src_paths: list[Path],
):
    """Clone the Android testbed, and stage source files into it.

    The testbed (and its `android.py` driver script) is xpython's own copy of
    CPython's testbed, rather than the copy in the Android Python archive.

    :param archive_path: The extracted Android Python archive directory
        (contains the `prefix/` directory and `android-env.sh` script used to
        build the testbed).
    :param work_path: The working directory to clone the testbed into.
    :param src_paths: Paths to copy into the cloned testbed's src directory.
    :raises RuntimeError: if running on GitHub actions on a macOS runner.
    """
    if host_platform() == "darwin" and "GITHUB_ACTIONS" in os.environ:
        raise RuntimeError(
            "GitHub Actions can't start an Android emulator on a macOS runner."
        )

    src_path = work_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)

    shutil.copy(TESTBED_RESOURCES / "android.py", work_path / "android.py")
    shutil.copytree(
        TESTBED_RESOURCES / "testbed", work_path / "testbed", dirs_exist_ok=True
    )
    (work_path / "prefix").symlink_to(archive_path / "prefix")
    (work_path / "android-env.sh").symlink_to(archive_path / "android-env.sh")

    # Before Python 3.13, Python doesn't redirect sys.stdout and sys.stderr to
    # the Android log, so the testbed driver wouldn't see any output. Add a
    # backport of that redirection to the testbed's site-packages.
    if not list((archive_path / "prefix" / "lib").glob("python*/_android_support.py")):
        shutil.copytree(
            TESTBED_RESOURCES / "legacy",
            work_path / "testbed" / "app" / "src" / "main" / "python",
            ignore=shutil.ignore_patterns("__pycache__"),
            dirs_exist_ok=True,
        )

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
    if "GITHUB_ACTIONS" in os.environ and host_platform() == "linux":
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
        sys.executable,
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

    result = subprocess.run(command, check=False, env=build_platform_env())
    return result.returncode
