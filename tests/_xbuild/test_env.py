import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from build.env import DefaultIsolatedEnv

from xbuild.env import XBuildIsolatedEnv


@pytest.fixture
def isolated_path(monkeypatch, tmp_path):
    """Replace the base isolated env setup, so that no real venv is
    created; the "isolated env" is just a path."""
    path = tmp_path / "build-env"

    def fake_enter(self):
        self._path = str(path)
        return self

    monkeypatch.setattr(DefaultIsolatedEnv, "__enter__", fake_enter)
    return path


@pytest.mark.parametrize(
    "cross_compiling",
    [pytest.param(None, id="native"), pytest.param(True, id="cross")],
)
def test_enter_converts_isolated_env(monkeypatch, isolated_path, cross_compiling):
    """The isolated environment is converted using the resolved config,
    whether or not xbuild is running in a cross-platform environment."""
    if cross_compiling is None:
        monkeypatch.delattr(sys, "cross_compiling", raising=False)
    else:
        monkeypatch.setattr(sys, "cross_compiling", cross_compiling, raising=False)
    cross_venv = Mock()

    env = XBuildIsolatedEnv(installer="pip", cross_venv=cross_venv)

    assert env.__enter__() is env
    cross_venv.convert.assert_called_once_with(Path(isolated_path))


def test_uv_unsupported():
    """uv can't be used as the installer."""
    with pytest.raises(RuntimeError, match="Can't support uv"):
        XBuildIsolatedEnv(installer="uv", cross_venv=Mock())
