import sys

import platformdirs
import pytest

from xvenv.fetch import default_arch, python_version_string, resolve_cache_dir


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
