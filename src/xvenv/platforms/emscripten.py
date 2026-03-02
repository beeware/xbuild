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

    context["platform_extra"] = f"""
    @monkeypatch(platform)
    def libc_ver() -> int:
        return ("emscripten", "{emscripten_version}")
"""
