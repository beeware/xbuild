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


def config_path(extracted_dir, version_info, arch: str):
    raise NotImplementedError(
        "xvenv does not yet know how to configure a Python build for emscripten."
    )
