from xvenv.convert import localized_vars


def test_android_style_tool_paths_are_stripped():
    """CC/AR sharing an absolute NDK-style toolchain directory are reduced
    to bare tool names; prefix substitution still applies elsewhere."""
    orig_vars = {
        "prefix": "/usr/local",
        "BINDIR": "/usr/local/bin",
        "CC": (
            "/Users/msmith/Library/Android/sdk/ndk/27.3.13750724/"
            "toolchains/llvm/prebuilt/darwin-x86_64/bin/"
            "aarch64-linux-android21-clang"
        ),
        "AR": (
            "/Users/msmith/Library/Android/sdk/ndk/27.3.13750724/"
            "toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-ar"
        ),
    }

    result = localized_vars(orig_vars, "/slice/path")

    assert result["CC"] == "aarch64-linux-android21-clang"
    assert result["AR"] == "llvm-ar"
    # Unrelated prefix-based substitution still happens.
    assert result["BINDIR"] == "/slice/path/bin"


def test_config_args_embedded_cc_path_is_stripped():
    """A CC=... fragment embedded inside a larger string (like
    CONFIG_ARGS) is stripped the same way as a standalone CC value."""
    tool_dir = (
        "/Users/msmith/Library/Android/sdk/ndk/27.3.13750724/"
        "toolchains/llvm/prebuilt/darwin-x86_64/bin"
    )
    orig_vars = {
        "prefix": "/usr/local",
        "CC": f"{tool_dir}/aarch64-linux-android21-clang",
        "CONFIG_ARGS": (
            "'--host=aarch64-linux-android' "
            f"'CC={tool_dir}/aarch64-linux-android21-clang' "
            "'--without-ensurepip'"
        ),
    }

    result = localized_vars(orig_vars, "/slice/path")

    assert result["CONFIG_ARGS"] == (
        "'--host=aarch64-linux-android' "
        "'CC=aarch64-linux-android21-clang' "
        "'--without-ensurepip'"
    )


def test_ios_style_bare_cc_is_not_modified():
    """When CC has no directory component (the iOS shape), no toolchain
    stripping occurs at all - only the existing prefix substitution."""
    orig_vars = {
        "prefix": "/usr/local",
        "BINDIR": "/usr/local/bin",
        "CC": "arm64-apple-ios-simulator-clang",
        "AR": "arm64-apple-ios-simulator-ar",
    }

    result = localized_vars(orig_vars, "/slice/path")

    assert result["CC"] == "arm64-apple-ios-simulator-clang"
    assert result["AR"] == "arm64-apple-ios-simulator-ar"
    assert result["BINDIR"] == "/slice/path/bin"


def test_missing_cc_key_does_not_crash():
    """If CC isn't present at all, localized_vars() still works and
    applies its existing prefix substitution normally."""
    orig_vars = {
        "prefix": "/usr/local",
        "BINDIR": "/usr/local/bin",
    }

    result = localized_vars(orig_vars, "/slice/path")

    assert result["BINDIR"] == "/slice/path/bin"


def test_similar_but_distinct_path_is_not_affected():
    """A value that shares a string prefix with the toolchain directory,
    but isn't actually inside it, must not be modified."""
    orig_vars = {
        "prefix": "/usr/local",
        "CC": "/opt/ndk/bin/clang",
        "UNRELATED": "/opt/ndk/binaries/foo",
    }

    result = localized_vars(orig_vars, "/slice/path")

    assert result["CC"] == "clang"
    assert result["UNRELATED"] == "/opt/ndk/binaries/foo"
