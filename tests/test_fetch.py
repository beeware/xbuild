import sys
import tarfile
from pathlib import Path
from unittest import mock

import platformdirs
import pytest

from xvenv.fetch import (
    default_arch,
    fetch_python,
    python_version_string,
    resolve_cache_dir,
)


def test_resolve_cache_dir_explicit_arg_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("XBUILD_CACHE", str(tmp_path / "from-env"))
    explicit = tmp_path / "from-arg"

    result = resolve_cache_dir(explicit)

    assert result == explicit
    assert explicit.is_dir()


def test_resolve_cache_dir_env_var_used_when_no_arg(tmp_path, monkeypatch):
    from_env = tmp_path / "from-env"
    monkeypatch.setenv("XBUILD_CACHE", str(from_env))

    result = resolve_cache_dir(None)

    assert result == from_env
    assert from_env.is_dir()


def test_resolve_cache_dir_falls_back_to_platformdirs(tmp_path, monkeypatch):
    monkeypatch.delenv("XBUILD_CACHE", raising=False)
    fallback = tmp_path / "platformdirs-cache"
    monkeypatch.setattr(platformdirs, "user_cache_dir", lambda appname: str(fallback))

    result = resolve_cache_dir(None)

    assert result == fallback
    assert fallback.is_dir()


def test_resolve_cache_dir_creates_missing_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("XBUILD_CACHE", raising=False)
    target = tmp_path / "does" / "not" / "exist" / "yet"

    result = resolve_cache_dir(target)

    assert result == target
    assert target.is_dir()


@pytest.mark.parametrize(
    "version_info,expected",
    [
        (
            sys.version_info.__replace__(
                major=3, minor=14, micro=7, releaselevel="final", serial=0
            ),
            "3.14.7",
        ),
        (
            sys.version_info.__replace__(
                major=3, minor=15, micro=0, releaselevel="candidate", serial=2
            ),
            "3.15.0rc2",
        ),
        (
            sys.version_info.__replace__(
                major=3, minor=15, micro=0, releaselevel="alpha", serial=1
            ),
            "3.15.0a1",
        ),
        (
            sys.version_info.__replace__(
                major=3, minor=15, micro=0, releaselevel="beta", serial=3
            ),
            "3.15.0b3",
        ),
    ],
)
def test_python_version_string(version_info, expected):
    assert python_version_string(version_info) == expected


@pytest.mark.parametrize(
    "platform_name,host_machine,expected",
    [
        ("ios", "arm64", "arm64_iphonesimulator"),
        ("ios", "aarch64", "arm64_iphonesimulator"),
        ("ios", "x86_64", "x86_64_iphonesimulator"),
        ("ios", "AMD64", "x86_64_iphonesimulator"),
        ("android", "arm64", "aarch64"),
        ("android", "aarch64", "aarch64"),
        ("android", "x86_64", "x86_64"),
        ("android", "AMD64", "x86_64"),
    ],
)
def test_default_arch(platform_name, host_machine, expected, monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: host_machine)

    assert default_arch(platform_name) == expected


def test_default_arch_unknown_host_machine_raises(monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "sparc64")

    with pytest.raises(ValueError, match="sparc64"):
        default_arch("ios")


def test_default_arch_emscripten_raises_not_implemented(monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "arm64")

    with pytest.raises(NotImplementedError):
        default_arch("emscripten")


def _make_archive(tmp_path, name, files):
    """Create a .tar.gz at tmp_path/name containing the given
    {relative_path: content} files, and return its Path."""
    src_dir = tmp_path / "_src_for_archive"
    src_dir.mkdir()
    for rel_path, content in files.items():
        full = src_dir / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

    archive_path = tmp_path / name
    with tarfile.open(archive_path, "w:gz") as tar:
        for rel_path in files:
            tar.add(src_dir / rel_path, arcname=rel_path)

    return archive_path


def test_fetch_python_skips_download_when_already_cached(tmp_path, monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "arm64")

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
        mock.patch("xvenv.fetch.python_version_string", return_value="3.14.7"),
        mock.patch("xvenv.fetch._current_version_info", return_value=version_info),
        mock.patch("urllib.request.urlretrieve") as urlretrieve,
    ):
        path, is_build_details = fetch_python("android", "aarch64", tmp_path)

    urlretrieve.assert_not_called()
    assert path == config_file
    assert is_build_details is True


def test_fetch_python_downloads_and_extracts_when_not_cached(tmp_path, monkeypatch):
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
        mock.patch("xvenv.fetch.python_version_string", return_value="3.14.7"),
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


def test_fetch_python_resolves_default_arch_when_arch_none(tmp_path, monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "arm64")
    version_info = sys.version_info.__replace__(
        major=3, minor=14, micro=7, releaselevel="final", serial=0
    )

    extracted_dir = tmp_path / "python-3.14.7-aarch64-linux-android"
    config_file = extracted_dir / "prefix" / "lib" / "python3.14" / "build-details.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("{}")

    with (
        mock.patch("xvenv.fetch.python_version_string", return_value="3.14.7"),
        mock.patch("xvenv.fetch._current_version_info", return_value=version_info),
        mock.patch("urllib.request.urlretrieve") as urlretrieve,
    ):
        path, _ = fetch_python("android", None, tmp_path)

    # arm64 host -> default_arch("android") == "aarch64", matching the
    # pre-populated cache dir name, so no download should occur.
    urlretrieve.assert_not_called()
    assert path == config_file


def test_fetch_python_invalid_arch_raises(tmp_path):
    with pytest.raises(ValueError, match="armv7l"):
        fetch_python("android", "armv7l", tmp_path)
