import sys
from pathlib import Path

VALID_ARCHES = ["aarch64", "x86_64"]


def download_url(version: str, arch: str, version_info=sys.version_info) -> str:
    """Compute the python.org download URL for an Android build.

    :param version: The python.org version string (e.g. ``"3.14.7"``).
    :param arch: One of the values in ``VALID_ARCHES``.
    :param version_info: The ``sys.version_info``-shaped value the version
        string was derived from, used to select pre-3.14 vs. 3.14+ URL
        conventions.
    :returns: The download URL.
    """
    if version_info[:2] < (3, 14):
        # TODO: real URL pattern for pre-3.14 Android builds. Placeholder only.
        return f"https://TODO.example/placeholder/android/{version}-{arch}.tar.gz"
    return (
        f"https://www.python.org/ftp/python/{version}/"
        f"python-{version}-{arch}-linux-android.tar.gz"
    )


def config_path(extracted_dir: Path, version_info, arch: str) -> Path:
    """Locate the sysconfig/build-details file inside an extracted Android
    archive.

    :param extracted_dir: The root of the extracted archive.
    :param version_info: A ``sys.version_info``-shaped value for the Python
        version the archive contains.
    :param arch: One of the values in ``VALID_ARCHES``, e.g. ``"aarch64"``.
    :returns: The path to ``build-details.json`` (Python 3.14+) or the
        legacy ``_sysconfigdata__android_*.py`` module (Python <3.14).
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

    context["platform_extra"] = f"""
    @monkeypatch(platform)
    def getandroidapilevel() -> int:
        return {api_level}

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
