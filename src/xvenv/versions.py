def version(version_info: tuple) -> str:
    """Return the full version number, including a/b/rc suffix."""
    version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    if version_info.releaselevel == "candidate":
        return f"{version_str}rc{version_info.serial}"
    elif version_info.releaselevel == "beta":
        return f"{version_str}b{version_info.serial}"
    elif version_info.releaselevel == "alpha":
        return f"{version_str}a{version_info.serial}"
    return version_str


def release(version_info: tuple) -> str:
    """Return the version number without any a/b/rc suffix."""
    return f"{version_info.major}.{version_info.minor}.{version_info.micro}"


def series(version_info: tuple) -> str:
    """Return the major.minor series (e.g., 3.14)."""
    return f"{version_info.major}.{version_info.minor}"
