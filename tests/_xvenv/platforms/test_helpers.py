import os
import sys

from xvenv.platforms import build_platform_env, host_platform


def test_host_platform_native(monkeypatch):
    """Outside a cross env, the host platform is sys.platform."""
    monkeypatch.delattr(sys, "_xvenv_host_platform", raising=False)

    assert host_platform() == sys.platform


def test_host_platform_in_cross_env(monkeypatch):
    """Inside a cross env, the recorded host platform is used, not the
    (patched) sys.platform."""
    monkeypatch.setattr(sys, "_xvenv_host_platform", "darwin", raising=False)
    monkeypatch.setattr(sys, "platform", "ios")

    assert host_platform() == "darwin"


def test_build_platform_env(monkeypatch):
    """The build platform environment disables cross env patches without
    modifying os.environ."""
    monkeypatch.setenv("SOME_VAR", "value")
    monkeypatch.setenv("XBUILD_ENV", "on")

    env = build_platform_env()

    assert env["XBUILD_ENV"] == "off"
    assert env["SOME_VAR"] == "value"
    assert os.environ["XBUILD_ENV"] == "on"
