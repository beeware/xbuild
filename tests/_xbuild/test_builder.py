import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from xbuild._builder import make_subprocess_runner
from xvenv.platforms import (
    ACTIVE_COMPILER_WRAPPER_DIR_VAR,
    BUILD_ENV_SCRIPTS_DIR_VAR,
    COMPILER_WRAPPER_DIR_VAR,
)


@pytest.fixture
def run(monkeypatch):
    """Capture the subprocess invocation made by the runner."""
    run = Mock()
    monkeypatch.setattr("xbuild._builder.subprocess.run", run)
    return run


def test_runner_without_wrappers(run, monkeypatch):
    """Without an active compiler wrapper directory, the runner behaves like
    the default: the environment plus extra_environ, unchanged."""
    monkeypatch.delenv(ACTIVE_COMPILER_WRAPPER_DIR_VAR, raising=False)
    monkeypatch.setenv("PATH", "/orig/bin")

    make_subprocess_runner()(["cmd"], "/cwd", {"PATH": "/isolated/bin:/orig/bin"})

    run.assert_called_once()
    (cmd,), kwargs = run.call_args
    assert cmd == ["cmd"]
    assert kwargs["cwd"] == "/cwd"
    assert kwargs["check"] is True
    assert kwargs["env"]["PATH"] == "/isolated/bin:/orig/bin"
    assert BUILD_ENV_SCRIPTS_DIR_VAR not in kwargs["env"]


def test_runner_ignores_user_wrapper_dir(run, monkeypatch):
    """A user-level `XBUILD_COMPILER_WRAPPER_DIR` (where wrappers *would* be
    created) doesn't inject wrappers into a build that didn't create any
    (e.g., an Android build)."""
    monkeypatch.delenv(ACTIVE_COMPILER_WRAPPER_DIR_VAR, raising=False)
    monkeypatch.setenv(COMPILER_WRAPPER_DIR_VAR, "/stale/wrappers")
    monkeypatch.setenv("PATH", "/orig/bin")

    make_subprocess_runner()(["cmd"])

    env = run.call_args.kwargs["env"]
    assert env["PATH"] == "/orig/bin"
    assert BUILD_ENV_SCRIPTS_DIR_VAR not in env


def test_runner_with_wrappers_isolated(run, monkeypatch):
    """With an active compiler wrapper directory, it is moved back to the
    front of PATH, and the isolated environment's bin directory is exposed to
    the wrappers."""
    monkeypatch.setenv(ACTIVE_COMPILER_WRAPPER_DIR_VAR, "/wrappers")
    monkeypatch.setenv("PATH", os.pathsep.join(["/wrappers", "/orig/bin"]))
    isolated_env = Mock(python_executable="/isolated/bin/python")

    make_subprocess_runner(isolated_env)(
        ["cmd"],
        None,
        {"PATH": os.pathsep.join(["/isolated/bin", "/wrappers", "/orig/bin"])},
    )

    env = run.call_args.kwargs["env"]
    assert env["PATH"] == os.pathsep.join(["/wrappers", "/isolated/bin", "/orig/bin"])
    assert env[BUILD_ENV_SCRIPTS_DIR_VAR] == str(Path("/isolated/bin"))


def test_runner_with_wrappers_current_env(run, monkeypatch):
    """Without an isolated environment, the current interpreter's bin
    directory is where build dependencies live."""
    monkeypatch.setenv(ACTIVE_COMPILER_WRAPPER_DIR_VAR, "/wrappers")
    monkeypatch.setenv("PATH", os.pathsep.join(["/wrappers", "/orig/bin"]))

    make_subprocess_runner()(["cmd"])

    env = run.call_args.kwargs["env"]
    assert env["PATH"] == os.pathsep.join(["/wrappers", "/orig/bin"])
    assert env[BUILD_ENV_SCRIPTS_DIR_VAR] == str(Path(sys.executable).parent)
