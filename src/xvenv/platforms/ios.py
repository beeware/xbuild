def extend_context(context, sysconfig):
    release = sysconfig["IPHONEOS_DEPLOYMENT_TARGET"]
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
