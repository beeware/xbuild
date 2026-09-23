import pytest

from xvenv.convert import localized_vars


@pytest.mark.parametrize(
    "tool_dir",
    [
        pytest.param(
            (
                "/Users/msmith/Library/Android/sdk/ndk/27.3.13750724/"
                "toolchains/llvm/prebuilt/darwin-x86_64/bin/"
            ),
            id="explicit-unofficial",
        ),
        pytest.param(
            (
                "/usr/local/lib/android/sdk/ndk/27.3.13750724/"
                "toolchains/llvm/prebuilt/linux-x86_64/bin/"
            ),
            id="explicit-official",
        ),
        pytest.param("", id="empty"),
    ],
)
def test_localize_vars(tool_dir):
    """Path definitions in sysconfigdata are cleaned."""
    orig_vars = {
        # The variables that are used as source data
        "prefix": "/path/to/build",
        "CC": (f"{tool_dir}aarch64-linux-android21-clang"),
        # Paths that are updated with the prefix.
        "BINDIR": "/path/to/build/bin",
        "BINLIBDEST": "/path/to/build/lib/python3.13",
        # "-F ." is expanded into the prefix.
        "BLDSHARED": (
            "arm64-apple-ios-simulator-clang -dynamiclib -F . -framework Python"
        ),
        # Paths that are updated
        "AR": (f"{tool_dir}llvm-ar"),
        "LDSHARED": (f"{tool_dir}aarch64-linux-android21-clang -Wl,--no-undefined -lm"),
        # Embedded paths are also replaced
        "CONFIG_ARGS": (
            "'--host=aarch64-linux-android' "
            f"'CC={tool_dir}aarch64-linux-android21-clang' "
            "'--without-ensurepip'"
        ),
    }

    result = localized_vars(orig_vars, "/slice/path")

    # Control variables are updated
    assert result["CC"] == "aarch64-linux-android21-clang"
    assert result["prefix"] == "/slice/path"

    # Prefix-based variables are updated
    assert result["BINDIR"] == "/slice/path/bin"
    assert result["BINLIBDEST"] == "/slice/path/lib/python3.13"

    # "-F ." is expanded into the prefix.
    assert result["BLDSHARED"] == (
        "arm64-apple-ios-simulator-clang -dynamiclib -F /slice/path -framework Python"
    )

    # toolchain based variables are updated
    assert result["AR"] == "llvm-ar"
    assert result["LDSHARED"] == "aarch64-linux-android21-clang -Wl,--no-undefined -lm"
    assert result["CONFIG_ARGS"] == (
        "'--host=aarch64-linux-android' "
        "'CC=aarch64-linux-android21-clang' "
        "'--without-ensurepip'"
    )


def test_missing_cc_key():
    """If CC isn't present, localized_vars() still works."""
    orig_vars = {
        "prefix": "/usr/local",
        "BINDIR": "/usr/local/bin",
    }

    result = localized_vars(orig_vars, "/slice/path")

    assert result["BINDIR"] == "/slice/path/bin"


def test_toolchain_dir_nested_under_prefix_is_still_stripped():
    """When the build's own install prefix is a literal path-prefix of the
    toolchain directory (as happens on "official" Linux-built Android
    slices, where ANDROID_HOME defaults to /usr/local/lib/android/sdk and
    the build's own prefix is also /usr/local), the toolchain directory
    must still be stripped from CC/AR/etc, not silently left in place
    because the prefix substitution already partially consumed it."""
    orig_vars = {
        "prefix": "/usr/local",
        "CC": (
            "/usr/local/lib/android/sdk/ndk/27.3.13750724/"
            "toolchains/llvm/prebuilt/linux-x86_64/bin/"
            "x86_64-linux-android24-clang"
        ),
        "AR": (
            "/usr/local/lib/android/sdk/ndk/27.3.13750724/"
            "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar"
        ),
    }

    result = localized_vars(orig_vars, "/slice/path")

    assert result["CC"] == "x86_64-linux-android24-clang"
    assert result["AR"] == "llvm-ar"
