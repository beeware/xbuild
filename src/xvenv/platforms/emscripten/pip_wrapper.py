"""A pip entry point for Emscripten cross-platform virtual environments.

This file is copied into the `bin` directory of an Emscripten cross venv (see
`xvenv.platforms.emscripten.install_pip_wrapper()`) and executed there by the
venv's own interpreter, so it must not import anything from xbuild/xvenv.

The venv's interpreter has already been patched (via `_cross_venv.pth`) so
that `sys.platform`, `platform`, and `sysconfig` all describe the Emscripten
target. This wrapper adds the pip-specific pieces on top of that:

* teach `packaging.tags` to produce the `pyodide_<abi>_wasm32` and
  `pyemscripten_<abi>_wasm32` platform tags, so pip will accept Pyodide wheels;
* make sure pip's vendored urllib3 doesn't take its Emscripten code path, since
  we are really running on a native host;
* repair the `pip*` scripts if `pip install --upgrade pip` has replaced them
  with stock console scripts.

Ported from pyodide-build's `pip_wrapper.py`
(https://github.com/pyodide/pyodide-build/blob/45caaca689e8366ea34811f920d246ee5323644c/pyodide_build/pip_wrapper.py);
the Pyodide-specific `python-host` shebang handling, `sys`/`platform`/`sysconfig`
patching (handled by xvenv) and Windows support have been removed.

Copyright (c) 2019-2026, Pyodide contributors. Modifications copyright (c)
2026, the xbuild contributors.

This Source Code Form is subject to the terms of the Mozilla Public License,
v. 2.0. If a copy of the MPL was not distributed with this file, You can obtain
one at https://mozilla.org/MPL/2.0/. See LICENSE.third-party in the xbuild
source distribution.
"""

import atexit
import errno
import os
import re
import sys
import sysconfig
from collections.abc import Iterator

# The name of this script, and of the launcher script that all `pip*` entries
# in the venv's bin directory should be symlinked to. These must match the
# names used by `xvenv.platforms.emscripten.install_pip_wrapper()`.
PIP_WRAPPER_NAME = "_pip-wrapper.py"
PIP_PATCHED_NAME = "pip_patched"

# The pip console scripts that a venv installs: `pip`, `pip3`, `pip3.14`.
# Anything else starting with "pip" (pip-compile, pipx, pip-audit, ...) is
# not ours to touch.
PIP_SCRIPT_RE = re.compile(r"pip(3(\.\d+)?)?")

###########################################################################
# urllib3
###########################################################################
# Newer versions of pip vendor an Emscripten-aware urllib3 which, when it sees
# `sys.platform == "emscripten"` at import time, swaps in a JavaScript
# fetch-based backend. That can't work: we are a native Python pretending to be
# Emscripten. Temporarily restore the host platform while urllib3 is imported.
_host_platform = getattr(sys, "_host_platform", None)
if _host_platform is not None:
    _target_platform = sys.platform
    sys.platform = _host_platform
    try:
        import pip._vendor.urllib3  # noqa: F401
    except ImportError:
        # pip no longer vendors urllib3 (or vendors it under another name);
        # whatever it uses instead is its own concern.
        pass
    finally:
        sys.platform = _target_platform

###########################################################################
# packaging.tags
###########################################################################
from pip._vendor.packaging import tags  # noqa: E402


def _generic_platforms() -> Iterator[str]:
    # `packaging.tags._generic_platforms` is private; fall back to doing what
    # it does if it disappears.
    generic = getattr(tags, "_generic_platforms", None)
    if generic is not None:
        yield from generic()
    else:
        yield tags._normalize_string(sysconfig.get_platform())


def _emscripten_platforms() -> Iterator[str]:
    """Platform tags for Pyodide/Emscripten wheels.

    Recent versions of `packaging` have an `_emscripten_platforms` function,
    but it only produces the `pyemscripten_` tag; older versions have nothing
    at all. Produce both the legacy `pyodide_` and current `pyemscripten_`
    tags, followed by the generic `emscripten_X_Y_Z_wasm32` tag.
    """
    abi_version = sysconfig.get_config_var(
        "PYEMSCRIPTEN_PLATFORM_VERSION"
    ) or sysconfig.get_config_var("PYODIDE_ABI_VERSION")
    if abi_version:
        yield f"pyodide_{abi_version}_wasm32"
        yield f"pyemscripten_{abi_version}_wasm32"
    yield from _generic_platforms()


tags._emscripten_platforms = _emscripten_platforms  # type: ignore[attr-defined]

# Packaging < 26.2 doesn't know to call `_emscripten_platforms()`; patch
# `platform_tags` so that it does.
_orig_platform_tags = tags.platform_tags


def platform_tags() -> Iterator[str]:
    if sys.platform == "emscripten":
        yield from _emscripten_platforms()
        return
    yield from _orig_platform_tags()


tags.platform_tags = platform_tags

###########################################################################
# Handle pip updates.
###########################################################################
# The pip executable should be a symlink to pip_patched. If it is not a link,
# or it is a symlink to something else, pip has been updated. We have to
# restore the correct value of pip. Iterate through all of the pip variants in
# the folder and remove them and replace with a symlink to pip_patched.
_venv_bin = os.path.dirname(os.path.abspath(__file__))
_pip_path = os.path.join(_venv_bin, "pip")
_pip_patched_path = os.path.join(_venv_bin, PIP_PATCHED_NAME)


def pip_is_okay() -> bool:
    try:
        return os.readlink(_pip_path) == _pip_patched_path
    except OSError as e:
        # EINVAL: the path exists but isn't a symlink (pip was upgraded).
        # ENOENT: there's no `pip` at all (only `pip3`?); treat as broken.
        if e.errno not in {errno.EINVAL, errno.ENOENT}:
            raise
    return False


def maybe_repair_after_pip_update() -> None:
    if pip_is_okay():
        return

    for name in os.listdir(_venv_bin):
        if not PIP_SCRIPT_RE.fullmatch(name):
            continue
        path = os.path.join(_venv_bin, name)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        os.symlink(_pip_patched_path, path)


atexit.register(maybe_repair_after_pip_update)

###########################################################################
# Run pip
###########################################################################
from pip._internal.cli.main import main  # noqa: E402

if __name__ == "__main__":
    sys.argv[0] = sys.argv[0].replace(PIP_WRAPPER_NAME, "pip")
    sys.exit(main())
