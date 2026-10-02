import io
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from xvenv.convert import (
    CrossVenvConfig,
    _record_source,
    in_cross_env,
    localized_vars,
)


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

    with pytest.raises(ValueError, match=r"Could not find .*does-not-exist\.json"):
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

    with pytest.raises(ValueError, match=r"Could not find .*sysconfigdata\.py"):
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


def _fake_venv(venv_path, version):
    """Create the minimal on-disk layout that `CrossVenvConfig.convert()`
    accepts as a virtual environment, returning the site-packages path."""
    series = ".".join(version.split(".")[:2])
    if sys.platform == "win32":
        (venv_path / "Scripts").mkdir(parents=True)
        (venv_path / "Scripts" / "python.exe").touch()
        site_packages = venv_path / "Lib" / "site-packages"
    else:
        (venv_path / "bin").mkdir(parents=True)
        (venv_path / "bin" / "python3").touch()
        site_packages = venv_path / "lib" / f"python{series}" / "site-packages"
    site_packages.mkdir(parents=True)
    (venv_path / "pyvenv.cfg").write_text(f"home = /usr/bin\nversion = {version}\n")
    return site_packages


def _android_sysconfigdata(tmp_path):
    """A legacy (Python 3.13) Android sysconfigdata file inside a fake archive."""
    path = (
        tmp_path
        / "archive"
        / "prefix"
        / "lib"
        / "python3.13"
        / "_sysconfigdata__android_aarch64-linux-android.py"
    )
    path.parent.mkdir(parents=True)
    build_time_vars = {
        "prefix": "/build/prefix",
        "LDLIBRARY": "libpython3.13.so",
        "VERSION": "3.13",
        "MULTIARCH": "aarch64-linux-android",
        "ANDROID_API_LEVEL": 24,
    }
    path.write_text(f"build_time_vars = {build_time_vars!r}\n")
    return path


def _android_build_details(tmp_path):
    """A Python 3.14 Android build-details.json (plus the sysconfig files it
    implies) inside a fake archive."""
    lib = tmp_path / "archive" / "prefix" / "lib" / "python3.14"
    lib.mkdir(parents=True)
    build_time_vars = {"prefix": "/build/prefix", "LDLIBRARY": "libpython3.14.so"}
    (lib / "_sysconfigdata__android_aarch64-linux-android.py").write_text(
        f"build_time_vars = {build_time_vars!r}\n"
    )
    (lib / "_sysconfig_vars__android_aarch64-linux-android.json").write_text(
        json.dumps(build_time_vars)
    )
    path = lib / "build-details.json"
    path.write_text(
        json.dumps(
            {
                "platform": "android-24-arm64_v8a",
                "implementation": {"_multiarch": "aarch64-linux-android"},
                "language": {"version": "3.14"},
                "abi": {"flags": []},
            }
        )
    )
    return path


def _sysconfig_config(sysconfigdata_path):
    return CrossVenvConfig(
        platform=None,
        arch=None,
        build_details_path=None,
        sysconfigdata_path=sysconfigdata_path,
        cache_path=None,
    )


def _build_details_config(build_details_path):
    return CrossVenvConfig(
        platform=None,
        arch=None,
        build_details_path=build_details_path,
        sysconfigdata_path=None,
        cache_path=None,
    )


def test_convert_records_sysconfig_source(tmp_path):
    """Converting from sysconfigdata records that path in pyvenv.cfg."""
    sysconfigdata_path = _android_sysconfigdata(tmp_path)
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.13.5")

    _sysconfig_config(sysconfigdata_path).convert(venv_path)

    lines = (venv_path / "pyvenv.cfg").read_text().splitlines()
    assert f"xvenv-sysconfig = {sysconfigdata_path.resolve()}" in lines
    assert not any(line.startswith("xvenv-build-details") for line in lines)
    # Pre-existing content is preserved.
    assert "home = /usr/bin" in lines
    assert "version = 3.13.5" in lines


def test_convert_records_build_details_source(tmp_path):
    """Converting from build-details.json records that path in pyvenv.cfg."""
    build_details_path = _android_build_details(tmp_path)
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.14.7")

    _build_details_config(build_details_path).convert(venv_path)

    lines = (venv_path / "pyvenv.cfg").read_text().splitlines()
    assert f"xvenv-build-details = {build_details_path.resolve()}" in lines
    assert not any(line.startswith("xvenv-sysconfig") for line in lines)


def test_convert_replaces_previous_source(tmp_path):
    """Re-converting a venv replaces any previously recorded source."""
    sysconfigdata_path = _android_sysconfigdata(tmp_path)
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.13.5")
    cfg_path = venv_path / "pyvenv.cfg"
    cfg_path.write_text(
        cfg_path.read_text()
        + "xvenv-build-details = /old/build-details.json\n"
        + "xvenv-sysconfig = /old/sysconfigdata.py\n"
    )

    _sysconfig_config(sysconfigdata_path).convert(venv_path)

    lines = cfg_path.read_text().splitlines()
    assert [line for line in lines if line.startswith("xvenv-")] == [
        f"xvenv-sysconfig = {sysconfigdata_path.resolve()}"
    ]


def test_from_venv_sysconfig(tmp_path):
    """A config can be reconstructed from a sysconfig-based cross venv."""
    sysconfigdata_path = _android_sysconfigdata(tmp_path)
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.13.5")
    _sysconfig_config(sysconfigdata_path).convert(venv_path)

    config = CrossVenvConfig.from_venv(venv_path)

    assert config.platform == "android"
    assert config.arch == "aarch64-linux-android"
    assert config.sysconfigdata_path == sysconfigdata_path.resolve()
    assert config.build_details_path is None
    assert config.archive_path == (tmp_path / "archive").resolve()


def test_from_venv_build_details(tmp_path):
    """A config can be reconstructed from a build-details-based cross venv."""
    build_details_path = _android_build_details(tmp_path)
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.14.7")
    _build_details_config(build_details_path).convert(venv_path)

    config = CrossVenvConfig.from_venv(venv_path)

    assert config.platform == "android"
    assert config.arch == "aarch64-linux-android"
    assert config.build_details_path == build_details_path.resolve()
    assert config.sysconfigdata_path is None


def test_from_venv_unrecorded(tmp_path):
    """A venv without a recorded source (e.g. made by xvenv <= 0.4.0) raises."""
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.13.5")

    with pytest.raises(ValueError, match="does not record the cross-platform"):
        CrossVenvConfig.from_venv(venv_path)


def test_from_venv_missing_pyvenv_cfg(tmp_path):
    """A directory with no pyvenv.cfg raises the same error."""
    with pytest.raises(ValueError, match="does not record the cross-platform"):
        CrossVenvConfig.from_venv(tmp_path)


def test_from_venv_recorded_file_missing(tmp_path):
    """If the recorded source file has since been deleted, a clear error
    is raised."""
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.13.5")
    cfg_path = venv_path / "pyvenv.cfg"
    missing = tmp_path / "gone" / "_sysconfigdata__android_aarch64-linux-android.py"
    cfg_path.write_text(cfg_path.read_text() + f"xvenv-sysconfig = {missing}\n")

    with pytest.raises(ValueError, match="Could not find") as exc_info:
        CrossVenvConfig.from_venv(venv_path)

    message = str(exc_info.value)
    assert str(cfg_path) in message
    assert str(missing) in message
    assert "Recreate the environment with xvenv" in message
    assert "--platform, --build-details or --sysconfig" in message


@pytest.fixture
def non_utf8_locale(monkeypatch):
    """Simulate a platform (e.g. Windows without UTF-8 mode) whose locale
    encoding isn't UTF-8, by making text I/O that doesn't specify an
    explicit encoding use cp1252."""
    real_text_encoding = io.text_encoding

    def text_encoding(encoding, stacklevel=2):
        if encoding is None:
            return "cp1252"
        return real_text_encoding(encoding, stacklevel)

    monkeypatch.setattr(io, "text_encoding", text_encoding)


def test_convert_records_non_ascii_source_as_utf8(tmp_path, non_utf8_locale):
    """A non-ASCII source path is written to pyvenv.cfg as UTF-8 (which is
    how CPython's site module reads it), regardless of the locale, and can be
    read back."""
    root = tmp_path / "J\u00fcrgen"
    sysconfigdata_path = _android_sysconfigdata(root)
    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.13.5")

    _sysconfig_config(sysconfigdata_path).convert(venv_path)

    content = (venv_path / "pyvenv.cfg").read_bytes().decode("utf-8")
    assert f"xvenv-sysconfig = {sysconfigdata_path.resolve()}" in content.splitlines()

    config = CrossVenvConfig.from_venv(venv_path)
    assert config.sysconfigdata_path == sysconfigdata_path.resolve()


def test_convert_writes_non_ascii_sysconfigdata_as_utf8(tmp_path, non_utf8_locale):
    """The localized sysconfigdata module (which Python imports as UTF-8
    source) is written as UTF-8 when it contains non-ASCII paths."""
    root = tmp_path / "J\u00fcrgen"
    sysconfigdata_path = _android_sysconfigdata(root)
    venv_path = tmp_path / "venv"
    site_packages = _fake_venv(venv_path, "3.13.5")

    _sysconfig_config(sysconfigdata_path).convert(venv_path)

    localized = site_packages / sysconfigdata_path.name
    assert "J\u00fcrgen" in localized.read_bytes().decode("utf-8")


def test_platform_config_relative_path_is_absolute(tmp_path, monkeypatch, mock_deps):
    """If the cache path is relative (e.g. `--cache ./cache`), the resolved
    configuration path, and the path recorded in pyvenv.cfg, are absolute."""
    monkeypatch.chdir(tmp_path)
    relative = mock_deps["config_path"].relative_to(tmp_path)
    mock_deps["fetch_python"].return_value = (relative, True)
    mock_deps["resolve_cache_path"].return_value = Path("cache")

    config = CrossVenvConfig(
        platform="android",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=Path("cache"),
    )

    assert config.build_details_path.is_absolute()
    assert config.build_details_path == mock_deps["config_path"].resolve()
    assert config.archive_path.is_absolute()

    venv_path = tmp_path / "venv"
    _fake_venv(venv_path, "3.14.7")
    _record_source(venv_path, config.build_details_path, config.sysconfigdata_path)
    lines = (venv_path / "pyvenv.cfg").read_text(encoding="utf-8").splitlines()
    assert f"xvenv-build-details = {mock_deps['config_path'].resolve()}" in lines


@pytest.mark.parametrize(("value", "expected"), [(True, True), (None, False)])
def test_in_cross_env(monkeypatch, value, expected):
    """in_cross_env() reflects sys.cross_compiling."""
    if value is None:
        monkeypatch.delattr(sys, "cross_compiling", raising=False)
    else:
        monkeypatch.setattr(sys, "cross_compiling", value, raising=False)

    assert in_cross_env() is expected


def test_from_current_env_not_cross(monkeypatch):
    """from_current_env() outside a cross env raises."""
    monkeypatch.delattr(sys, "cross_compiling", raising=False)

    with pytest.raises(ValueError, match="Not running in a cross-platform environment"):
        CrossVenvConfig.from_current_env()


def test_from_current_env_uses_sys_prefix(monkeypatch):
    """from_current_env() reads the config of the venv at sys.prefix."""
    monkeypatch.setattr(sys, "cross_compiling", True, raising=False)
    sentinel = Mock()
    from_venv = Mock(return_value=sentinel)
    monkeypatch.setattr(CrossVenvConfig, "from_venv", from_venv)

    assert CrossVenvConfig.from_current_env() is sentinel
    from_venv.assert_called_once_with(Path(sys.prefix))


def test_convert_uses_host_venv_layout(tmp_path, monkeypatch):
    """Inside a cross env, convert() finds the venv layout of the *host*
    platform, not of the (patched) sys.platform."""
    sysconfigdata_path = _android_sysconfigdata(tmp_path)
    venv_path = tmp_path / "venv"
    # Build the fake venv with the real host's layout before patching.
    site_packages = _fake_venv(venv_path, "3.13.5")
    host = sys.platform
    # Patch sys.platform to a value whose venv layout differs from the host's.
    monkeypatch.setattr(sys, "_xvenv_host_platform", host, raising=False)
    monkeypatch.setattr(sys, "platform", "android" if host == "win32" else "win32")

    _sysconfig_config(sysconfigdata_path).convert(venv_path)

    assert (site_packages / "_cross_android_aarch64_linux_android.py").is_file()


def test_convert_records_host_platform(tmp_path):
    """The generated cross-target module records the host platform before
    patching sys.platform."""
    sysconfigdata_path = _android_sysconfigdata(tmp_path)
    venv_path = tmp_path / "venv"
    site_packages = _fake_venv(venv_path, "3.13.5")

    _sysconfig_config(sysconfigdata_path).convert(venv_path)

    source = (site_packages / "_cross_android_aarch64_linux_android.py").read_text()
    record = "sys._xvenv_host_platform = sys.platform"
    patch = 'sys.platform = "android"'
    assert record in source
    assert source.index(record) < source.index(patch)
