"""Live, end-to-end verification of xpython's testbed execution.

Drives the real `xpython` CLI (no mocking) to actually run a small pytest
suite inside a real iOS Simulator / Android emulator, using real downloaded
official Python builds (cached via the same XBUILD_CACHE/platformdirs
resolution used elsewhere in this project).

Requires network access, and either a working Xcode installation (iOS) or
Android SDK + emulator support (Android).
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

IOS_SKIPS = [
    pytest.mark.skipif(
        sys.platform != "darwin",
        reason="iOS tests can only be run on macOS",
    ),
]
ANDROID_SKIPS = [
    pytest.mark.skipif(
        sys.version_info < (3, 13),
        reason="Android tests require Python 3.13+",
    ),
]


def _write_sample_test_suite(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "test_sample.py").write_text(
        textwrap.dedent(
            """
            import sys

            def test_platform_is_reported():
                assert sys.platform in ("ios", "android", "linux", "darwin")

            def test_simple_arithmetic():
                assert 1 + 1 == 2
            """
        )
    )


@pytest.mark.parametrize("arch", ["arm64-iphonesimulator"], ids=["ios-arm64-sim"])
@pytest.mark.parametrize("marks", [IOS_SKIPS])
def test_xpython_ios_runs_pytest_suite(tmp_path, arch, marks, request):
    for mark in marks:
        request.applymarker(mark)

    src_dir = tmp_path / "tests"
    _write_sample_test_suite(src_dir)
    work_dir = tmp_path / "work"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "xpython",
            "--platform",
            "ios",
            "--arch",
            arch,
            "--src",
            str(src_dir),
            "-d",
            "pytest",
            "--work-dir",
            str(work_dir),
            "-m",
            "pytest",
            "tests",
            "-v",
        ],
        check=False,
    )

    assert result.returncode == 0


@pytest.mark.parametrize("arch", ["aarch64"], ids=["android-aarch64"])
@pytest.mark.parametrize("marks", [ANDROID_SKIPS])
def test_xpython_android_runs_pytest_suite(tmp_path, arch, marks, request):
    for mark in marks:
        request.applymarker(mark)

    src_dir = tmp_path / "tests"
    _write_sample_test_suite(src_dir)
    work_dir = tmp_path / "work"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "xpython",
            "--platform",
            "android",
            "--arch",
            arch,
            "--src",
            str(src_dir),
            "-d",
            "pytest",
            "--work-dir",
            str(work_dir),
            "-m",
            "pytest",
            "tests",
            "-v",
        ],
        check=False,
    )

    assert result.returncode == 0
