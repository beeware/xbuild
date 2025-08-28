def extend_context(context, sysconfig):
    context["release"] = "4.0.12"

    context["os_sysname"] = "Emscripten"
    context["os_nodename"] = "emscripten"
    context["os_release"] = "4.0.12"
    context["os_version"] = "#1"

    context["platform_extra"] = """
    def cross_libc_ver() -> int:
        return ("emscripten", "4.0.12")

    platform.libc_ver = cross_libc_ver
"""
