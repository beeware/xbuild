import platformdirs

from xvenv.fetch import resolve_cache_dir


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
