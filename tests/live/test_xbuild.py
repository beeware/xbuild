"""Live, end-to-end verification that `xbuild` can build a real binary
wheel for a project containing a C extension, and that `xpython` can run
a test suite for that binary wheel.

Drives the real `xbuild` CLI (no mocking) against a real downloaded target
Python build, for the default/host-native architecture of each supported
platform. Requires network access (downloads real Python builds on first
run per platform/Python-version combination).

Unlike tests/live/test_xvenv.py (which only exercises xvenv's venv
metadata patching), this test performs a *real compilation* of a C
extension module for the target platform, and therefore has platform
preconditions beyond just "downloaded Python build available":

- iOS: requires Xcode command-line tools to be installed and selected.
- Android: requires ANDROID_HOME and JAVA_HOME to already be set, and the
  exact NDK version required by the downloaded Android Python build to
  already be installed under $ANDROID_HOME/ndk/<version>. No auto-install
  is attempted.

If a required precondition is missing, the test fails.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SAMPLE_PROJECTS = [
    pytest.param(Path(__file__).parents[1] / "samples" / "test1", id="test1"),
]

CASES = [
    pytest.param(
        "ios",
        id="ios",
        marks=[
            pytest.mark.skipif(
                sys.platform != "darwin",
                reason="iOS tests can only be run on macOS",
            ),
            pytest.mark.iOS,
        ],
    ),
    pytest.param(
        "android",
        id="android",
        marks=[
            pytest.mark.skipif(
                sys.platform == "win32",
                reason="Android xbuild tests cannot be run on Windows",
            ),
            pytest.mark.skipif(
                sys.version_info < (3, 13),
                reason="Android tests require Python 3.13+",
            ),
            pytest.mark.android,
        ],
    ),
]

_ANDROID_HOST_TRIPLETS = {
    "aarch64": "aarch64-linux-android",
    "x86_64": "x86_64-linux-android",
}
_NDK_VERSION_RE = re.compile(r"^ndk_version=(\S+)", re.MULTILINE)
_EXPORT_LINE_RE = re.compile(r"^(?:declare -x |export )?(\w+)=['\"]?(.*?)['\"]?$")


def _check_preconditions(platform_name):
    if platform_name == "ios":
        _check_preconditions_ios()
    elif platform_name == "android":
        _check_preconditions_android()
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


def _check_preconditions_android():
    if "ANDROID_HOME" not in os.environ:
        pytest.fail(
            "ANDROID_HOME environment variable is not set. It must point "
            "at an installed Android SDK."
        )
    if "JAVA_HOME" not in os.environ:
        pytest.fail(
            "JAVA_HOME environment variable is not set. It must point at "
            "an installed JDK."
        )


@pytest.mark.live
@pytest.mark.parametrize("platform_name", CASES)
@pytest.mark.parametrize("sample_project", SAMPLE_PROJECTS)
def test_build_wheel(tmp_path, platform_name, sample_project):
    """xbuild can build a real binary wheel for a project containing a C
    extension, for the default arch of the current host."""
    # Fail fast on preconditions that don't require a download first.
    _check_preconditions(platform_name)

    project_dir = tmp_path / sample_project.name
    shutil.copytree(sample_project, project_dir)
    out_dir = tmp_path / "dist"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "xbuild",
            project_dir,
            "--platform",
            platform_name,
            "-o",
            out_dir,
        ],
        check=True,
    )

    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    assert not wheels[0].name.endswith("-none-any.whl"), (
        f"{wheels[0].name} is not a binary wheel"
    )

    # Now run the test suite for the project, installing the 'test' dependency
    # group, and installing the binary wheel from the build output directory.
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "xpython",
                "--platform",
                platform_name,
                "--src",
                project_dir / "tests",
                "--group",
                "test",
                "--dependency",
                sample_project.name,
                "--find-links",
                out_dir,
                "--",
                "-m",
                "pytest",
                "tests",
            ],
            check=True,
        )
        assert result.returncode == 0
    except subprocess.CalledProcessError:
        # Android tests can't be run in CI on macOS because GitHub Actions doesn't
        # support acceleration.
        is_ci = "GITHUB_ACTIONS" in os.environ
        is_android = platform_name == "android"
        is_macOS = sys.platform == "darwin"
        if is_ci and is_android and is_macOS:
            print("Running on GitHub Actions; Android xpython test aborted.")
        else:
            raise
