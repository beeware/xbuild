import json
from unittest.mock import Mock

import pytest

from xvenv.convert import CrossVenvConfig, localized_vars


@pytest.fixture
def mock_deps(monkeypatch, tmp_path):
    cache_path = tmp_path / "cache"
    archive_path = cache_path / "python-3.14.7-aarch64-linux-android"
    config_path = archive_path / "prefix" / "lib" / "python3.14" / "build-details.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "platform": "android-24-arm64_v8a",
                "implementation": {"_multiarch": "aarch64-linux-android"},
            }
        )
    )

    mocks = {
        "config_path": config_path,
        "archive_path": archive_path,
        "cache_path": cache_path,
        "create": Mock(),
        "resolve_cache_path": Mock(return_value=cache_path),
        "resolve_arch": Mock(return_value="aarch64"),
        "fetch_python": Mock(return_value=(config_path, True)),
        "use_archive_path": Mock(return_value=(config_path, True)),
    }
    monkeypatch.setattr("xvenv.convert.venv.create", mocks["create"])
    monkeypatch.setattr("xvenv.convert.resolve_cache_path", mocks["resolve_cache_path"])
    monkeypatch.setattr("xvenv.convert.resolve_arch", mocks["resolve_arch"])
    monkeypatch.setattr("xvenv.convert.fetch_python", mocks["fetch_python"])
    monkeypatch.setattr("xvenv.convert.use_archive_path", mocks["use_archive_path"])
    return mocks


@pytest.fixture
def mock_config(mock_deps):
    return CrossVenvConfig(
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )


@pytest.fixture
def mock_convert(monkeypatch, mock_config):
    convert = Mock()
    monkeypatch.setattr(mock_config, "convert", convert)
    return convert


def test_creates_venv_when_missing(tmp_path, mock_config, mock_deps, mock_convert):
    """`create()` will create the cross environment if it doesn't exist."""
    venv_path = tmp_path / "x-venv"

    mock_config.create(venv_path)

    mock_deps["create"].assert_called_once_with(venv_path, with_pip=True)
    mock_convert.assert_called_once_with(venv_path)


def test_reuses_existing_venv(tmp_path, mock_config, mock_deps, mock_convert):
    """`create()` will reuse an exist cross environment if it exists."""
    venv_path = tmp_path / "x-venv"
    venv_path.mkdir()

    mock_config.create(venv_path)

    mock_deps["create"].assert_not_called()
    mock_convert.assert_called_once_with(venv_path)


@pytest.mark.parametrize("with_pip", [True, False])
def test_with_pip_passthrough(tmp_path, mock_config, mock_deps, mock_convert, with_pip):
    """`with_pip=False` is passed through to `venv.create()`."""
    venv_path = tmp_path / "x-venv"

    mock_config.create(venv_path, with_pip=with_pip)

    mock_deps["create"].assert_called_once_with(venv_path, with_pip=with_pip)
    mock_convert.assert_called_once_with(venv_path)


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


@pytest.mark.parametrize(
    ("full_platform", "multiarch", "description"),
    [
        (
            "android-24-arm64_v8a",
            "aarch64-linux-android",
            "Android aarch64-linux-android",
        ),
        (
            "ios-13.0-arm64-iphonesimulator",
            "arm64-iphonesimulator",
            "iOS arm64-iphonesimulator",
        ),
    ],
)
def test_config_description(full_platform, multiarch, description, mock_deps):
    """Config description correctly capitalizes platform for display."""
    mock_deps["config_path"].write_text(
        json.dumps(
            {
                "platform": full_platform,
                "implementation": {"_multiarch": multiarch},
            }
        )
    )

    config = CrossVenvConfig(
        platform=full_platform.split("-")[0],
        arch=multiarch.split("-")[0],
        archive_path=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )
    assert config.description == description


def test_config_via_platform(tmp_path, mock_deps):
    """Configuring via platform resolves arch, downloads, and produces a config."""
    config = CrossVenvConfig(
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )

    mock_deps["resolve_cache_path"].assert_called_once_with(None)
    mock_deps["resolve_arch"].assert_called_once_with("android", None)
    mock_deps["fetch_python"].assert_called_once_with(
        "android", "aarch64", mock_deps["cache_path"]
    )
    assert config.platform == "android"
    assert config.arch == "aarch64-linux-android"
    assert config.build_details_path == mock_deps["config_path"]
    assert config.sysconfigdata_path is None
    assert config.archive_path == mock_deps["archive_path"]
    assert config.platform_module.__name__ == "xvenv.platforms.android"


def test_config_via_archive_path(tmp_path, mock_deps):
    """If an archive is provided, Python won't be downloaded."""
    supplied_archive = tmp_path / "my-existing-build"
    supplied_archive.mkdir()

    CrossVenvConfig(
        platform="android",
        arch=None,
        archive_path=supplied_archive,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )

    mock_deps["resolve_cache_path"].assert_not_called()
    mock_deps["fetch_python"].assert_not_called()
    mock_deps["use_archive_path"].assert_called_once_with(
        "android", "aarch64", supplied_archive.resolve()
    )


def test_config_via_build_details_path(tmp_path):
    """An environment can be configured with a build-details.json."""
    build_details_path = tmp_path / "build-details.json"
    build_details_path.write_text(
        json.dumps(
            {
                "platform": "ios-13.0-arm64-iphonesimulator",
                "implementation": {"_multiarch": "arm64-iphonesimulator"},
            }
        )
    )
    archive_root = tmp_path / "Python.xcframework" / "ios-arm64_x86_64-simulator"
    archive_root.mkdir(parents=True)

    config = CrossVenvConfig(
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


def test_config_via_sysconfigdata_path(tmp_path):
    """An environment can be configured with a sysconfigdata file."""
    sysconfigdata_path = (
        tmp_path
        / "prefix"
        / "lib"
        / "python3.13"
        / "_sysconfigdata__android_aarch64-linux-android.py"
    )
    sysconfigdata_path.parent.mkdir(parents=True)
    sysconfigdata_path.write_text("build_time_vars = {}")

    config = CrossVenvConfig(
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


def test_config_no_path():
    """An environment requires at least one configuration option."""
    with pytest.raises(
        ValueError,
        match="Must provide path to either build_details.json or sysconfigdata",
    ):
        CrossVenvConfig(
            platform=None,
            arch=None,
            build_details_path=None,
            sysconfigdata_path=None,
            cache_path=None,
        )


def test_config_unknown_platfo4m(tmp_path):
    """An unrecognized platform name raises a clear ValueError."""
    build_details_path = tmp_path / "build-details.json"
    build_details_path.write_text(
        json.dumps(
            {
                "platform": "bogus-1.0-x86_64",
                "implementation": {"_multiarch": "x86_64-bogus"},
            }
        )
    )

    with pytest.raises(
        ValueError,
        match="Don't know how to build a cross-venv for bogus",
    ):
        CrossVenvConfig(
            platform=None,
            arch=None,
            build_details_path=build_details_path,
            sysconfigdata_path=None,
            cache_path=None,
        )


def test_config_missing_build_details_file(tmp_path):
    """A build_details_path that doesn't exist raises a clear ValueError."""
    missing = tmp_path / "does-not-exist.json"

    with pytest.raises(ValueError, match=rf"Could not find {missing}"):
        CrossVenvConfig(
            platform=None,
            arch=None,
            build_details_path=missing,
            sysconfigdata_path=None,
            cache_path=None,
        )


def test_config_missing_sysconfigdata_file(tmp_path):
    """A sysconfigdata_path that doesn't exist raises a clear ValueError."""
    missing = tmp_path / "sysconfigdata.py"

    with pytest.raises(ValueError, match=rf"Could not find {missing}"):
        CrossVenvConfig(
            platform=None,
            arch=None,
            build_details_path=None,
            sysconfigdata_path=missing,
            cache_path=None,
        )


def test_prepare_env_dispatches_to_platform_module(tmp_path, mock_config):
    """`prepare_env()` delegates to the platform module."""
    fake_platform_module = Mock()
    fake_platform_module.prepare_env.return_value = {"CC": "fake-clang"}

    mock_config.platform_module = fake_platform_module

    result = mock_config.prepare_env()

    fake_platform_module.prepare_env.assert_called_once_with(mock_config)
    assert result == {"CC": "fake-clang"}
