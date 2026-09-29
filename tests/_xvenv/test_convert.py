from pathlib import Path
from unittest.mock import Mock

import pytest

from xvenv.convert import CrossVenvConfig, create_cross_venv, localized_vars


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
        "use_archive_path": Mock(return_value=(config_path, True)),
        "convert_venv": Mock(
            return_value=CrossVenvConfig(
                platform="Android",
                arch="aarch64-linux-android",
                archive_path=archive_path,
                venv_path=tmp_path / "x-venv",
            )
        ),
    }
    monkeypatch.setattr("xvenv.convert.venv.create", mocks["create"])
    monkeypatch.setattr("xvenv.convert.resolve_cache_path", mocks["resolve_cache_path"])
    monkeypatch.setattr("xvenv.convert.resolve_arch", mocks["resolve_arch"])
    monkeypatch.setattr("xvenv.convert.fetch_python", mocks["fetch_python"])
    monkeypatch.setattr("xvenv.convert.use_archive_path", mocks["use_archive_path"])
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


def test_archive_path_routes_to_use_archive_path(tmp_path, mock_deps):
    """When archive_path is given, use_archive_path() is called instead of
    resolve_cache_path()/fetch_python(), and the result flows into
    convert_venv() the same way fetch_python()'s result would."""
    venv_path = tmp_path / "x-venv"
    supplied_archive = tmp_path / "my-existing-build"
    supplied_archive.mkdir()

    create_cross_venv(
        venv_path,
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
        archive_path=supplied_archive,
    )

    mock_deps["resolve_cache_path"].assert_not_called()
    mock_deps["fetch_python"].assert_not_called()
    mock_deps["use_archive_path"].assert_called_once_with(
        "android", "aarch64", supplied_archive.resolve()
    )
    mock_deps["convert_venv"].assert_called_once()


def test_archive_path_is_resolved(tmp_path, mock_deps):
    """A relative archive_path is resolved to an absolute path before being
    passed to use_archive_path(), matching how build_details_path/
    sysconfigdata_path are already resolved elsewhere in this function."""
    venv_path = tmp_path / "x-venv"
    (tmp_path / "relative-build").mkdir()

    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        create_cross_venv(
            venv_path,
            platform="android",
            arch=None,
            build_details_path=None,
            sysconfigdata_path=None,
            cache_path=None,
            archive_path=Path("relative-build"),
        )
    finally:
        os.chdir(old_cwd)

    mock_deps["use_archive_path"].assert_called_once_with(
        "android", "aarch64", tmp_path / "relative-build"
    )


def test_cross_venv_config_description():
    """description capitalizes platform for display, with iOS
    special-cased to avoid the naive .capitalize() result "Ios"."""
    from xvenv.convert import CrossVenvConfig

    android_config = CrossVenvConfig(
        platform="android",
        arch="aarch64-linux-android",
        archive_path=Path("/some/archive"),
        platform_module=None,
        build_details_path=None,
        sysconfigdata_path=Path("/some/sysconfigdata.py"),
    )
    assert android_config.description == "Android aarch64-linux-android"

    ios_config = CrossVenvConfig(
        platform="ios",
        arch="arm64-iphonesimulator",
        archive_path=Path("/some/archive"),
        platform_module=None,
        build_details_path=None,
        sysconfigdata_path=Path("/some/sysconfigdata.py"),
    )
    assert ios_config.description == "iOS arm64-iphonesimulator"

    emscripten_config = CrossVenvConfig(
        platform="emscripten",
        arch="wasm32",
        archive_path=Path("/some/archive"),
        platform_module=None,
        build_details_path=None,
        sysconfigdata_path=Path("/some/sysconfigdata.py"),
    )
    assert emscripten_config.description == "Emscripten wasm32"


@pytest.fixture
def mock_resolve_deps(monkeypatch, tmp_path):
    """Mock resolve_arch/fetch_python/use_archive_path/resolve_cache_path
    for resolve_cross_venv_config()'s --platform branch."""
    cache_path = tmp_path / "cache"
    archive_dir = cache_path / "python-3.14.7-aarch64-linux-android"
    config_path = archive_dir / "prefix" / "lib" / "python3.14" / "build-details.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{"platform": "android-24-arm64_v8a", '
        '"implementation": {"_multiarch": "aarch64-linux-android"}}'
    )

    mocks = {
        "resolve_cache_path": Mock(return_value=cache_path),
        "resolve_arch": Mock(return_value="aarch64"),
        "fetch_python": Mock(return_value=(config_path, True)),
        "use_archive_path": Mock(return_value=(config_path, True)),
    }
    monkeypatch.setattr("xvenv.convert.resolve_cache_path", mocks["resolve_cache_path"])
    monkeypatch.setattr("xvenv.convert.resolve_arch", mocks["resolve_arch"])
    monkeypatch.setattr("xvenv.convert.fetch_python", mocks["fetch_python"])
    monkeypatch.setattr("xvenv.convert.use_archive_path", mocks["use_archive_path"])
    mocks["cache_path"] = cache_path
    mocks["archive_dir"] = archive_dir
    mocks["config_path"] = config_path
    return mocks


def test_resolve_cross_venv_config_via_platform(tmp_path, mock_resolve_deps):
    """--platform resolves arch, downloads/caches, and produces a config
    pointing at the resulting build-details.json."""
    from xvenv.convert import resolve_cross_venv_config

    config = resolve_cross_venv_config(
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )

    mock_resolve_deps["resolve_cache_path"].assert_called_once_with(None)
    mock_resolve_deps["resolve_arch"].assert_called_once_with("android", None)
    mock_resolve_deps["fetch_python"].assert_called_once_with(
        "android", "aarch64", mock_resolve_deps["cache_path"]
    )
    assert config.platform == "android"
    assert config.arch == "aarch64-linux-android"
    assert config.build_details_path == mock_resolve_deps["config_path"]
    assert config.sysconfigdata_path is None
    assert config.archive_path == mock_resolve_deps["archive_dir"]
    assert config.platform_module.__name__ == "xvenv.platforms.android"


def test_resolve_cross_venv_config_via_archive_path(tmp_path, mock_resolve_deps):
    """archive_path routes through use_archive_path(), not
    resolve_cache_path()/fetch_python()."""
    from xvenv.convert import resolve_cross_venv_config

    supplied_archive = tmp_path / "my-existing-build"
    supplied_archive.mkdir()

    resolve_cross_venv_config(
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
        archive_path=supplied_archive,
    )

    mock_resolve_deps["resolve_cache_path"].assert_not_called()
    mock_resolve_deps["fetch_python"].assert_not_called()
    mock_resolve_deps["use_archive_path"].assert_called_once_with(
        "android", "aarch64", supplied_archive.resolve()
    )


def test_resolve_cross_venv_config_via_build_details_path(tmp_path):
    """An explicit build_details_path (no --platform) is used directly,
    with no download/cache/archive resolution."""
    from xvenv.convert import resolve_cross_venv_config

    build_details_path = tmp_path / "build-details.json"
    build_details_path.write_text(
        '{"platform": "ios-13.0-arm64-iphonesimulator", '
        '"implementation": {"_multiarch": "arm64-iphonesimulator"}}'
    )
    archive_root = tmp_path / "Python.xcframework" / "ios-arm64_x86_64-simulator"
    archive_root.mkdir(parents=True)

    config = resolve_cross_venv_config(
        platform=None,
        arch=None,
        build_details_path=build_details_path,
        sysconfigdata_path=None,
        cache_path=None,
    )

    assert config.platform == "ios"
    assert config.arch == "arm64-iphonesimulator"
    assert config.build_details_path == build_details_path.resolve()
    assert config.sysconfigdata_path is None
    assert config.platform_module.__name__ == "xvenv.platforms.ios"


def test_resolve_cross_venv_config_via_sysconfigdata_path(tmp_path):
    """An explicit sysconfigdata_path (no --platform) has platform/multiarch
    extracted from its filename."""
    from xvenv.convert import resolve_cross_venv_config

    sysconfigdata_path = (
        tmp_path
        / "prefix"
        / "lib"
        / "python3.13"
        / "_sysconfigdata__android_aarch64-linux-android.py"
    )
    sysconfigdata_path.parent.mkdir(parents=True)
    sysconfigdata_path.write_text("build_time_vars = {}")

    config = resolve_cross_venv_config(
        platform=None,
        arch=None,
        build_details_path=None,
        sysconfigdata_path=sysconfigdata_path,
        cache_path=None,
    )

    assert config.platform == "android"
    assert config.arch == "aarch64-linux-android"
    assert config.sysconfigdata_path == sysconfigdata_path.resolve()
    assert config.build_details_path is None
    assert config.platform_module.__name__ == "xvenv.platforms.android"


def test_resolve_cross_venv_config_neither_path_given():
    """Neither platform, build_details_path, nor sysconfigdata_path raises
    a clear ValueError."""
    from xvenv.convert import resolve_cross_venv_config

    with pytest.raises(
        ValueError,
        match="Must provide path to either build_details.json or sysconfigdata",
    ):
        resolve_cross_venv_config(
            platform=None,
            arch=None,
            build_details_path=None,
            sysconfigdata_path=None,
            cache_path=None,
        )


def test_resolve_cross_venv_config_unknown_platform(tmp_path):
    """An unrecognized platform name (from build_details_path's contents)
    raises a clear ValueError."""
    from xvenv.convert import resolve_cross_venv_config

    build_details_path = tmp_path / "build-details.json"
    build_details_path.write_text(
        '{"platform": "bogus-1.0-x86_64", '
        '"implementation": {"_multiarch": "x86_64-bogus"}}'
    )

    with pytest.raises(
        ValueError, match="Don't know how to build a cross-venv for bogus"
    ):
        resolve_cross_venv_config(
            platform=None,
            arch=None,
            build_details_path=build_details_path,
            sysconfigdata_path=None,
            cache_path=None,
        )


def test_resolve_cross_venv_config_missing_build_details_file(tmp_path):
    """A build_details_path that doesn't exist raises a clear ValueError."""
    from xvenv.convert import resolve_cross_venv_config

    missing = tmp_path / "does-not-exist.json"

    with pytest.raises(ValueError, match=f"Could not find {missing}"):
        resolve_cross_venv_config(
            platform=None,
            arch=None,
            build_details_path=missing,
            sysconfigdata_path=None,
            cache_path=None,
        )
