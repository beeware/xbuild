import sys
from pathlib import Path

VALID_ARCHES = ["arm64_iphonesimulator", "x86_64_iphonesimulator", "arm64_iphoneos"]


def download_url(version: str, version_info=sys.version_info) -> str:
    """Compute the python.org download URL for the iOS XCframework build.

    :param version: The python.org version string (e.g. ``"3.15.0rc2"``).
    :param version_info: The ``sys.version_info``-shaped value the version
        string was derived from, used to select pre-3.14 vs. 3.14+ URL
        conventions.
    :returns: The download URL.
    """
    if version_info[:2] < (3, 14):
        # TODO: real URL pattern for pre-3.14 iOS builds (different source,
        # different filename/layout convention). Placeholder only.
        return f"https://TODO.example/placeholder/iOS/{version}.tar.gz"
    return (
        f"https://www.python.org/ftp/python/{version}/"
        f"python-{version}-iOS-XCframework.tar.gz"
    )


def config_path(extracted_dir: Path, version_info, arch: str) -> Path:
    """Locate the sysconfig/build-details file inside an extracted iOS
    XCframework archive.

    :param extracted_dir: The root of the extracted archive.
    :param version_info: A ``sys.version_info``-shaped value for the Python
        version the archive contains.
    :param arch: One of the values in ``VALID_ARCHES``, e.g.
        ``"arm64_iphonesimulator"``.
    :returns: The path to ``build-details.json`` (Python 3.14+) or the
        legacy ``_sysconfigdata__ios_*.py`` module (Python <3.14).
    """
    cpu, sdk = arch.rsplit("_", 1)
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
