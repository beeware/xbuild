"""Live, end-to-end verification that `xbuild` can build a real binary
wheel for a project containing a C extension.

Drives the real `xbuild` CLI (no mocking) against a real downloaded target
Python build, for the default/host-native architecture of each supported
platform. Requires network access (downloads real Python builds on first
run per platform/Python-version combination; cached afterwards via the
existing XBUILD_CACHE/platformdirs resolution in
xvenv.fetch.resolve_cache_dir()).

Unlike tests/live/test_xvenv.py (which only exercises xvenv's venv
metadata patching), this test performs a *real compilation* of a C
extension module for the target platform, and therefore has platform
preconditions beyond just "downloaded Python build available":

- iOS: requires Xcode command-line tools to be installed and selected.
- Android: requires ANDROID_HOME and JAVA_HOME to already be set, and the
  exact NDK version required by the downloaded Android Python build to
  already be installed under $ANDROID_HOME/ndk/<version>. No auto-install
  is attempted.

If a required precondition is missing, the test fails loudly via
pytest.fail() with a specific, actionable message - it does not skip
silently.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from xvenv.fetch import fetch_python, resolve_arch, resolve_cache_dir

SAMPLE_PROJECT = Path(__file__).parents[1] / "samples" / "test1"

CASES = []
if sys.platform == "darwin":
    # iOS builds can only be performed on macOS.
    CASES.append(pytest.param("ios", id="ios"))


def _check_preconditions(platform_name):
    if platform_name == "ios":
        _check_preconditions_ios()
    else:
        raise AssertionError(f"no precondition check for {platform_name!r}")


def _check_preconditions_ios():
    result = subprocess.run(["xcode-select", "-p"], capture_output=True, check=False)
    if result.returncode != 0:
        pytest.fail(
            "Xcode command-line tools are required to build for iOS. "
            "Run `xcode-select --install` or select an Xcode install with "
            "`sudo xcode-select -s /Applications/Xcode.app`."
        )


def _build_env(platform_name, config_path, arch):
    if platform_name == "ios":
        return _build_env_ios(config_path)
    else:
        raise AssertionError(f"no environment builder for {platform_name!r}")


def _build_env_ios(config_path):
    # config_path is e.g.
    # .../Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/python3.13/
    #     _sysconfigdata__ios_arm64-iphonesimulator.py
    # or, for Python >= 3.14:
    # .../Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/python3.14/
    #     build-details.json
    # In both cases, the slice's own `bin/` directory (containing the
    # `arm64-apple-ios-*-clang` etc. shims) is 2 levels up from config_path's
    # parent.
    slice_bin_dir = config_path.parents[2] / "bin"
    venv_bin_dir = Path(sys.executable).parent

    return {
        "PATH": os.pathsep.join(
            [
                str(venv_bin_dir),
                str(slice_bin_dir),
                "/usr/bin",
                "/bin",
                "/usr/sbin",
                "/sbin",
                "/Library/Apple/usr/bin",
            ]
        ),
    }


@pytest.mark.parametrize("platform_name", CASES)
def test_build_wheel(tmp_path, platform_name):
    """xbuild can build a real binary wheel for a project containing a C
    extension, for the default arch of the current host."""
    # Fail fast on preconditions that don't require a download first.
    _check_preconditions(platform_name)

    arch = resolve_arch(platform_name, None)
    cache_dir = resolve_cache_dir(None)
    config_path, _ = fetch_python(platform_name, arch, cache_dir)

    project_dir = tmp_path / "test1"
    shutil.copytree(SAMPLE_PROJECT, project_dir)
    out_dir = tmp_path / "dist"

    env = _build_env(platform_name, config_path, arch)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "xbuild",
            str(project_dir),
            "--platform",
            platform_name,
            "--arch",
            arch,
            "--cache",
            str(cache_dir),
            "-o",
            str(out_dir),
        ],
        env=env,
        check=True,
    )

    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    assert not wheels[0].name.endswith("-none-any.whl"), (
        f"{wheels[0].name} is not a binary wheel"
    )
