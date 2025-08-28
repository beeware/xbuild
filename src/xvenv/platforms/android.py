def extend_context(context, sysconfig):
    # Convert the API level into a release number
    api_level = int(sysconfig["ANDROID_API_LEVEL"])
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
    context["release"] = release

    # The Linux kernel version and release are unlikely to be
    # significant, but return realistic values anyway (from an
    # API level 24 emulator).
    context["os_sysname"] = "Linux"
    context["os_nodename"] = "localhost"
    context["os_release"] = "3.18.91+"
    context["os_version"] = "#1 SMP PREEMPT Tue Jan 9 20:35:43 UTC 2018"

    context["platform_extra"] = f"""
    def cross_getandroidapilevel() -> int:
        return {api_level}

    def cross_android_ver(
        release="",
        api_level=0,
        manufacturer="",
        model="",
        device="",
        is_emulator=False
    ):
        if release == "":
            release = "{release}"
        if api_level == "":
            release = "{api_level}"
        if manufacturer == "":
            manufacturer = "Google"
        if model == "":
            model = "sdk_gphone64"
        if device == "":
            device = "emu64"

        return platform.AndroidVer(
            release, api_level, manufacturer, model, device, True
        )

    platform.getandroidapilevel = cross_getandroidapilevel
    platform.android_ver = cross_android_ver
"""
