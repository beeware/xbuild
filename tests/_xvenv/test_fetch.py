import sys
from pathlib import Path
from unittest import mock

import platformdirs
import pytest

from xvenv.fetch import (
    fetch_python,
    resolve_arch,
    resolve_cache_dir,
)

from ..utils import _make_archive


def test_resolve_cache_dir_explicit_arg_wins(tmp_path, monkeypatch):
    """An explicit cache directory takes precedence."""
    monkeypatch.setenv("XBUILD_CACHE", str(tmp_path / "from-env"))
    explicit = tmp_path / "from-arg"

    result = resolve_cache_dir(explicit)

    assert result == explicit
    assert explicit.is_dir()


def test_resolve_cache_dir_env_var_used_when_no_arg(tmp_path, monkeypatch):
    """The environment variable takes precedence if there's no explicit cache dir."""
    from_env = tmp_path / "from-env"
    monkeypatch.setenv("XBUILD_CACHE", str(from_env))

    result = resolve_cache_dir(None)

    assert result == from_env
    assert from_env.is_dir()


def test_resolve_cache_dir_falls_back_to_platformdirs(tmp_path, monkeypatch):
    """Platformdirs is used if there's no explicit location or environment variable."""
    monkeypatch.delenv("XBUILD_CACHE", raising=False)
    fallback = tmp_path / "platformdirs-cache"
    monkeypatch.setattr(platformdirs, "user_cache_dir", lambda appname: str(fallback))

    result = resolve_cache_dir(None)

    assert result == fallback
    assert fallback.is_dir()


def test_resolve_cache_dir_creates_missing_directory(tmp_path, monkeypatch):
    """The cache directory will be created if it doesn't exist yet."""
    monkeypatch.delenv("XBUILD_CACHE", raising=False)
    target = tmp_path / "does" / "not" / "exist" / "yet"
    assert not target.is_dir()

    result = resolve_cache_dir(target)

    assert result == target
    assert target.is_dir()


@pytest.mark.parametrize(
    ("platform_name", "host_machine", "expected"),
    [
        # iOS arch detection
        pytest.param("ios", "arm64", "arm64-iphonesimulator", id="ios-arm64"),
        pytest.param("ios", "x86_64", "x86_64-iphonesimulator", id="ios-x86_64"),
        # Android arch detection
        pytest.param("android", "arm64", "aarch64", id="android-arm64"),
        pytest.param("android", "aarch64", "aarch64", id="android-aarch64"),
        pytest.param("android", "x86_64", "x86_64", id="android-x86_64"),
        pytest.param("android", "AMD64", "x86_64", id="android-AMD64"),
        pytest.param("android", "ARM64", "aarch64", id="android-ARM64"),
        # Emscripten arch detection
        pytest.param("emscripten", "arm64", "wasm32", id="emscripten-arm64"),
        pytest.param("emscripten", "aarch64", "wasm32", id="emscripten-aarch64"),
        pytest.param("emscripten", "x86_64", "wasm32", id="emscripten-x86_64"),
        pytest.param("emscripten", "AMD64", "wasm32", id="emscripten-AMD64"),
        pytest.param("emscripten", "ARM64", "wasm32", id="emscripten-ARM64"),
    ],
)
def test_resolve_default_arch(platform_name, host_machine, expected, monkeypatch):
    """The default architecture can be detected for each platform."""
    monkeypatch.setattr("platform.machine", lambda: host_machine)

    assert resolve_arch(platform_name, None) == expected


@pytest.mark.parametrize(
    ("platform_name", "arch"),
    [
        # iOS explicit architectures
        pytest.param("ios", "arm64-iphonesimulator", id="ios-arm64-sim-native"),
        pytest.param("ios", "x86_64-iphonesimulator", id="ios-arm64-sim-cross"),
        pytest.param("ios", "x86_64-iphonesimulator", id="ios-x86_64-sim-cross"),
        pytest.param("ios", "x86_64-iphonesimulator", id="ios-x86_64-sim-native"),
        pytest.param("ios", "arm64-iphoneos", id="ios-device-arm64"),
        pytest.param("ios", "arm64-iphoneos", id="ios-device-x86_64"),
        # Android explicit architecture
        pytest.param("android", "aarch64", id="android-arm64"),
        pytest.param("android", "aarch64", id="android-aarch64"),
        pytest.param("android", "x86_64", id="android-x86_64"),
        pytest.param("android", "x86_64", id="android-AMD64"),
        pytest.param("android", "aarch64", id="android-ARM64"),
        # Emscripten explicit architecture
        pytest.param("emscripten", "wasm32", id="emscripten-arm64"),
        pytest.param("emscripten", "wasm32", id="emscripten-aarch64"),
        pytest.param("emscripten", "wasm32", id="emscripten-x86_64"),
        pytest.param("emscripten", "wasm32", id="emscripten-AMD64"),
        pytest.param("emscripten", "wasm32", id="emscripten-ARM64"),
    ],
)
@pytest.mark.parametrize(
    "host_machine",
    ["arm64", "aarch64", "ARM64", "AMD64", "x86_64"],
)
def test_resolve_arch_explicit(platform_name, arch, host_machine, monkeypatch):
    """An explicit architecture will be honored."""
    monkeypatch.setattr("platform.machine", lambda: host_machine)

    assert resolve_arch(platform_name, arch) == arch


@pytest.mark.parametrize("platform_name", ["ios", "android", "emscripten"])
def test_default_arch_unknown_arch(monkeypatch, platform_name):
    """An unknown architecture raises an error."""
    with pytest.raises(ValueError, match="sparc64"):
        resolve_arch(platform_name, "sparc64")


@pytest.mark.parametrize("platform_name", ["ios", "android", "emscripten"])
def test_default_arch_unknown_host_machine(monkeypatch, platform_name):
    """An unknown host machine type raises an error."""
    monkeypatch.setattr("platform.machine", lambda: "sparc64")

    with pytest.raises(ValueError, match="sparc64"):
        resolve_arch(platform_name, None)


def test_skip_download_when_cached(tmp_path, monkeypatch):
    """If the required directory already exists, it is used."""
    # Pre-populate the cache with an already-"extracted" directory matching
    # what android.config_path() expects for the current interpreter version.
    extracted_dir = tmp_path / "python-3.14.7-aarch64-linux-android"
    version_info = sys.version_info.__replace__(
        major=3, minor=14, micro=7, releaselevel="final", serial=0
    )
    config_file = extracted_dir / "prefix" / "lib" / "python3.14" / "build-details.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    with (
        mock.patch("xvenv.fetch._current_version_info", return_value=version_info),
        mock.patch("urllib.request.urlretrieve") as urlretrieve,
    ):
        path, is_build_details = fetch_python("android", "aarch64", tmp_path)

    urlretrieve.assert_not_called()
    assert path == config_file
    assert is_build_details is True


def test_skip_download_when_cached_not_unpacked(tmp_path, monkeypatch):
    """If the required directory already exists, it is used."""
    # Pre-populate the cache with an already-downloaded, but not extracted directory
    _make_archive(
        tmp_path,
        "python-3.14.7-aarch64-linux-android.tar.gz",
        {
            "prefix/lib/python3.14/build-details.json": "{}",
        },
    )

    extracted_dir = tmp_path / "python-3.14.7-aarch64-linux-android"
    version_info = sys.version_info.__replace__(
        major=3, minor=14, micro=7, releaselevel="final", serial=0
    )
    config_file = extracted_dir / "prefix" / "lib" / "python3.14" / "build-details.json"

    with (
        mock.patch("xvenv.fetch._current_version_info", return_value=version_info),
        mock.patch("urllib.request.urlretrieve") as urlretrieve,
    ):
        path, is_build_details = fetch_python("android", "aarch64", tmp_path)

    urlretrieve.assert_not_called()
    assert path == config_file
    assert is_build_details is True


def test_fetch_python(tmp_path, monkeypatch):
    """If the required file doesn't exist, it is downloaded."""
    monkeypatch.setattr("platform.machine", lambda: "arm64")
    version_info = sys.version_info.__replace__(
        major=3, minor=14, micro=7, releaselevel="final", serial=0
    )

    fake_archive = _make_archive(
        tmp_path,
        "fake-source.tar.gz",
        {
            "prefix/lib/python3.14/build-details.json": "{}",
        },
    )

    def fake_urlretrieve(url, filename):
        # Simulate the download by copying our pre-built fake archive to the
        # requested destination path.
        Path(filename).write_bytes(Path(fake_archive).read_bytes())

    with (
        mock.patch("xvenv.fetch._current_version_info", return_value=version_info),
        mock.patch(
            "urllib.request.urlretrieve", side_effect=fake_urlretrieve
        ) as urlretrieve,
    ):
        path, is_build_details = fetch_python("android", "aarch64", tmp_path)

    urlretrieve.assert_called_once()
    called_url = urlretrieve.call_args.args[0]
    assert called_url == (
        "https://www.python.org/ftp/python/3.14.7/"
        "python-3.14.7-aarch64-linux-android.tar.gz"
    )

    expected_extracted_dir = tmp_path / "python-3.14.7-aarch64-linux-android"
    assert expected_extracted_dir.is_dir()
    assert (tmp_path / "python-3.14.7-aarch64-linux-android.tar.gz").is_file()
    assert path == (
        expected_extracted_dir / "prefix" / "lib" / "python3.14" / "build-details.json"
    )
    assert is_build_details is True
