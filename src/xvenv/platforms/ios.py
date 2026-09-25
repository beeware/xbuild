from pathlib import Path

from xvenv import versions

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
            "3.11": "b10",
            "3.12": "b10",
            "3.13": "b15",
            "3.14": "b11",
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
