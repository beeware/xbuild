"""Live, end-to-end verification of xvenv's cross-platform venv conversion.

Drives the real `xvenv` CLI (no mocking) to create real cross-platform
venvs against real downloaded official Python builds, for both of xvenv's
documented usages, then runs a real nested pytest suite inside each
resulting cross-venv's own interpreter to verify its self-reported
sys/platform/sysconfig metadata against hardcoded ground-truth values.

Requires network access (downloads real Python builds on first run per
platform/arch/Python-version combination; cached afterwards via the
existing XBUILD_CACHE/platformdirs resolution in xvenv.fetch.resolve_cache_dir()).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
INNER_PATCHED_DIR = _HERE / "_inner" / "patched"
INNER_DISABLED_DIR = _HERE / "_inner" / "disabled"
EXPECTED_VALUES_DIR = _HERE / "expected_values"

CASES = []
if sys.platform == "darwin":
    # iOS tests can only run on macOS
    CASES.extend(
        [
            pytest.param("ios", "arm64-iphonesimulator", id="ios-arm64-simulator"),
            pytest.param("ios", "x86_64-iphonesimulator", id="ios-x86_64-simulator"),
            pytest.param("ios", "arm64-iphoneos", id="ios-arm64-device"),
        ]
    )

if sys.version_info >= (3, 13, 0):
    # Android is only supported from 3.13 onwards
    CASES.extend(
        [
            pytest.param("android", "aarch64", id="android-aarch64"),
            pytest.param("android", "x86_64", id="android-x86_64"),
        ]
    )


def _expected_values_path() -> Path:
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    path = EXPECTED_VALUES_DIR / f"{version}.toml"
    if not path.is_file():
        pytest.fail(
            f"No expected-values file for Python {version}; "
            f"add tests/live/expected_values/{version}.toml"
        )
    return path


def _install_pytest(venv_python: Path) -> None:
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "pytest"],
        env={**os.environ, "XBUILD_ENV": "off"},
        check=True,
        capture_output=True,
        text=True,
    )


def _run_inner_suite(venv_python: Path, inner_dir: Path, extra_env: dict) -> None:
    result = subprocess.run(
        [str(venv_python), "-m", "pytest", str(inner_dir), "-vv"],
        env={**os.environ, **extra_env},
        check=False,
    )
    assert result.returncode == 0, "inner test suite failed"


def _verify_patched(
    venv_path: Path,
    expected_path: Path,
    platform_name: str,
    arch: str,
) -> None:
    venv_python = venv_path / "bin" / "python"
    _install_pytest(venv_python)
    _run_inner_suite(
        venv_python,
        INNER_PATCHED_DIR,
        {
            "_XBUILD_EXPECTED_VALUES_PATH": str(expected_path),
            "_XBUILD_PLATFORM": platform_name,
            "_XBUILD_ARCH": arch,
        },
    )


def test_convert_existing_venv(tmp_path):
    """xvenv converts an already-existing native venv in place."""
    expected_path = _expected_values_path()

    venv_path = tmp_path / "x-venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    # Convert to an iOS
    subprocess.run(
        [
            sys.executable,
            "-m",
            "xvenv",
            "--platform",
            "ios",
            "--arch",
            "arm64-iphonesimulator",
            str(venv_path),
        ],
        check=True,
    )

    _verify_patched(
        venv_path,
        expected_path,
        platform_name="ios",
        arch="arm64-iphonesimulator",
    )


@pytest.mark.parametrize(("platform_name", "arch"), CASES)
def test_create_xvenv(tmp_path, platform_name, arch):
    """xvenv can creates a brand new cross-platform venv."""
    expected_path = _expected_values_path()

    venv_path = tmp_path / "x-venv"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "xvenv",
            "--platform",
            platform_name,
            "--arch",
            arch,
            str(venv_path),
        ],
        check=True,
    )

    _verify_patched(venv_path, expected_path, platform_name=platform_name, arch=arch)

    # Disabled-mode check: reuses this same cross-venv rather than creating
    # a third one, since disabled-mode behavior doesn't depend on how the
    # venv was originally created.
    _run_inner_suite(
        venv_path / "bin" / "python",
        INNER_DISABLED_DIR,
        {"XBUILD_ENV": "off"},
    )
