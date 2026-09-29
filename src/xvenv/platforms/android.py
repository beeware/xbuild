import json
import os
import re
from pathlib import Path

from xvenv import versions
from xvenv.fetch import parse_sysconfigdata

_NDK_VERSION_RE = re.compile(r"^ndk_version=(\S+)", re.MULTILINE)

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


def _api_level(config) -> int:
    """Read the minimum Android API level directly from whichever config
    source is present, without going through the generic
    build_details_from_sysconfigdata()/extend_context() machinery (that
    machinery exists for convert_venv()'s templating needs, and
    reconstructs far more than prepare_env() actually needs here)."""
    if config.build_details_path:
        with open(config.build_details_path) as fp:
            build_details = json.load(fp)
        return int(build_details["platform"].split("-")[1])
    sysconfigdata = parse_sysconfigdata(config.sysconfigdata_path)
    return sysconfigdata.build_time_vars["ANDROID_API_LEVEL"]


def prepare_env(config) -> dict[str, str]:
    """Prepare CC/AR/CXX/etc. environment variables for compiling Android
    native code, equivalent to sourcing the bundled android-env.sh.

    :param config: The resolved `xvenv.convert.CrossVenvConfig`.
    :returns: A dict of environment variables (AR, AS, CC, CXX, LD, NM,
        RANLIB, READELF, STRIP, CFLAGS, LDFLAGS, CXXFLAGS, CPU_COUNT,
        and -- if a prefix/ directory exists in the archive --
        PKG_CONFIG/PKG_CONFIG_LIBDIR).
    :raises ValueError: if ANDROID_HOME isn't set, the archive's
        android-env.sh can't be found/parsed, or the required NDK
        version isn't already installed under
        $ANDROID_HOME/ndk/<version>.
    """
    host = config.arch

    android_home = os.environ.get("ANDROID_HOME")
    if not android_home:
        raise ValueError(
            "ANDROID_HOME environment variable is not set. It must "
            "point at an installed Android SDK."
        )

    api_level = _api_level(config)

    env_script = config.archive_path / "android-env.sh"
    if not env_script.is_file():
        raise ValueError(f"Could not find {env_script}")
    match = _NDK_VERSION_RE.search(env_script.read_text())
    if not match:
        raise ValueError(f"Could not find ndk_version= in {env_script}")
    ndk_version = match[1]

    ndk_dir = Path(android_home) / "ndk" / ndk_version
    if not ndk_dir.is_dir():
        raise ValueError(
            f"Android NDK {ndk_version} is required (as specified by "
            f"{env_script}), but was not found at {ndk_dir}. Install "
            f'it with `sdkmanager "ndk;{ndk_version}"`, or use '
            "`$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager` to "
            "list available versions."
        )

    clang_triplet = (
        "armv7a-linux-androideabi" if host == "arm-linux-androideabi" else host
    )

    try:
        toolchain = next((ndk_dir / "toolchains" / "llvm" / "prebuilt").glob("*"))
    except StopIteration:
        raise ValueError(
            f"Could not find a prebuilt toolchain under "
            f"{ndk_dir}/toolchains/llvm/prebuilt"
        ) from None

    def tool(name: str) -> str:
        return str(toolchain / "bin" / name)

    cc = tool(f"{clang_triplet}{api_level}-clang")
    env = {
        "AR": tool("llvm-ar"),
        "AS": tool("llvm-as"),
        "CC": cc,
        "CXX": f"{cc}++",
        "LD": tool("ld"),
        "NM": tool("llvm-nm"),
        "RANLIB": tool("llvm-ranlib"),
        "READELF": tool("llvm-readelf"),
        "STRIP": tool("llvm-strip"),
    }
    for path in env.values():
        if not Path(path).exists():
            raise ValueError(f"{path} does not exist")

    cflags = "-D__BIONIC_NO_PAGE_SIZE_MACRO"
    ldflags = (
        "-Wl,--build-id=sha1 -Wl,--no-rosegment -Wl,-z,max-page-size=16384 "
        "-Wl,--no-undefined -lm"
    )
    if host == "arm-linux-androideabi":
        cflags += " -march=armv7-a -mthumb"

    prefix = config.archive_path / "prefix"
    if prefix.exists():
        abs_prefix = str(prefix.resolve())
        cflags += f" -I{abs_prefix}/include"
        ldflags += f" -L{abs_prefix}/lib"
        env["PKG_CONFIG"] = "pkg-config --define-prefix"
        env["PKG_CONFIG_LIBDIR"] = f"{abs_prefix}/lib/pkgconfig"

    env.update(
        {
            "CFLAGS": cflags,
            "LDFLAGS": ldflags,
            "CXXFLAGS": cflags,
            "CPU_COUNT": str(os.cpu_count() or 1),
        }
    )
    return env
