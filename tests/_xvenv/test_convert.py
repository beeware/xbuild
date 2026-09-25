from unittest.mock import Mock

import pytest

from xvenv.convert import create_cross_venv, localized_vars


@pytest.fixture
def mock_deps(monkeypatch, tmp_path):
    # config_path must live under the *resolved cache dir* (tmp_path /
    # "cache"), not some unrelated directory -- create_cross_venv() derives
    # archive_path by walking config_path back up to its ancestor directly
    # under resolved_cache_path, so config_path.relative_to(resolved_cache_path)
    # must actually succeed.
    cache_path = tmp_path / "cache"
    archive_path = cache_path / "python-3.14.7-aarch64-linux-android"
    config_path = archive_path / "prefix" / "lib" / "python3.14" / "build-details.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}")

    mocks = {
        "create": Mock(),
        "resolve_cache_path": Mock(return_value=cache_path),
        "resolve_arch": Mock(return_value="aarch64"),
        "fetch_python": Mock(return_value=(config_path, True)),
        "convert_venv": Mock(return_value=("Android", "aarch64-linux-android")),
    }
    monkeypatch.setattr("xvenv.convert.venv.create", mocks["create"])
    monkeypatch.setattr("xvenv.convert.resolve_cache_path", mocks["resolve_cache_path"])
    monkeypatch.setattr("xvenv.convert.resolve_arch", mocks["resolve_arch"])
    monkeypatch.setattr("xvenv.convert.fetch_python", mocks["fetch_python"])
    monkeypatch.setattr("xvenv.convert.convert_venv", mocks["convert_venv"])
    mocks["cache_path"] = cache_path
    mocks["archive_path"] = archive_path
    return mocks


def test_creates_venv_when_missing(tmp_path, mock_deps):
    """create_cross_venv() creates the venv if it doesn't exist, and returns
    the description + archive dir."""
    venv_path = tmp_path / "x-venv"

    result = create_cross_venv(
        venv_path,
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )

    mock_deps["create"].assert_called_once_with(venv_path, with_pip=True)
    mock_deps["resolve_cache_path"].assert_called_once_with(None)
    mock_deps["resolve_arch"].assert_called_once_with("android", None)
    mock_deps["fetch_python"].assert_called_once_with(
        "android", "aarch64", mock_deps["cache_path"]
    )
    mock_deps["convert_venv"].assert_called_once()
    assert result.description == "Android aarch64-linux-android"
    assert result.platform == "Android"
    assert result.arch == "aarch64-linux-android"
    assert result.venv_path == venv_path
    assert result.archive_path == mock_deps["archive_path"]


def test_reuses_existing_venv(tmp_path, mock_deps):
    """create_cross_venv() does not re-create an already-existing venv."""
    venv_path = tmp_path / "x-venv"
    venv_path.mkdir()

    create_cross_venv(
        venv_path,
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )

    mock_deps["create"].assert_not_called()


def test_without_pip_passthrough(tmp_path, mock_deps):
    """with_pip=False is passed through to venv.create()."""
    venv_path = tmp_path / "x-venv"

    create_cross_venv(
        venv_path,
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
        with_pip=False,
    )

    mock_deps["create"].assert_called_once_with(venv_path, with_pip=False)


def test_archive_path_derived_from_config_path(tmp_path, mock_deps):
    """archive_path is the top-level extracted directory, not the config
    file's immediate parent -- i.e. it walks back up to the directory
    fetch_python() extracted the archive into."""
    venv_path = tmp_path / "x-venv"

    result = create_cross_venv(
        venv_path,
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )

    # The fixture's config_path is archive_path/prefix/lib/python3.14/build-details.json
    assert result.archive_path == mock_deps["archive_path"]


@pytest.mark.parametrize(
    "tool_dir",
    [
        pytest.param(
            (
                "/Users/msmith/Library/Android/sdk/ndk/27.3.13750724/"
                "toolchains/llvm/prebuilt/darwin-x86_64/bin/"
            ),
            id="user-tools",
        ),
        pytest.param(
            (
                "/usr/local/lib/android/sdk/ndk/27.3.13750724/"
                "toolchains/llvm/prebuilt/linux-x86_64/bin/"
            ),
            id="system-tools",
        ),
        pytest.param("", id="no-tools"),
    ],
)
@pytest.mark.parametrize("prefix_dir", ["/path/to/build", "/usr/local"])
def test_localize_vars(tool_dir, prefix_dir):
    """Path definitions in sysconfigdata are cleaned."""
    orig_vars = {
        # The variables that are used as source data
        "prefix": prefix_dir,
        "CC": f"{tool_dir}aarch64-linux-android21-clang",
        # Paths that are updated with the prefix.
        "BINDIR": f"{prefix_dir}/bin",
        "BINLIBDEST": f"{prefix_dir}/lib/python3.13",
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
        "LDLIBRARY": "libPython.so",
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

    # LDLIBRARY has been removed.
    assert "LDLIBRARY" not in result


def test_missing_cc_key():
    """If CC isn't present, localized_vars() still works."""
    orig_vars = {
        "prefix": "/usr/local",
        "BINDIR": "/usr/local/bin",
        "LDLIBRARY": "libPython.so",
    }

    result = localized_vars(orig_vars, "/slice/path")

    assert result["BINDIR"] == "/slice/path/bin"
