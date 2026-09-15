"""Verifies the cross-platform metadata patched into a converted xvenv
cross-venv, by running *inside* that cross-venv's own interpreter.

Run via: <cross-venv>/bin/python -m pytest tests/live/_inner/patched
Requires: XBUILD_EXPECTED_VALUES_PATH env var pointing at the TOML file
for the running Python's minor version (see tests/live/expected_values/).
"""

import os
import platform
import sys
import sysconfig
import tomllib
from pathlib import Path

import pytest

CROSS_PLATFORM = os.environ["_XBUILD_CROSS_PLATFORM"]
CROSS_MULTIARCH = os.environ["_XBUILD_CROSS_MULTIARCH"]

TOML_PATH = Path(os.environ["_XBUILD_EXPECTED_VALUES_PATH"])
COMMON_TOML_PATH = (
    Path(os.environ["_XBUILD_EXPECTED_VALUES_PATH"]).parent / "common.toml"
)

ALL_COMMON_EXPECTED = tomllib.loads(COMMON_TOML_PATH.read_text())
ALL_EXPECTED = tomllib.loads(TOML_PATH.read_text())
EXPECTED = ALL_COMMON_EXPECTED[CROSS_PLATFORM][CROSS_MULTIARCH]
EXPECTED.update(ALL_EXPECTED.get(CROSS_PLATFORM, {}).get(CROSS_MULTIARCH, {}))


def test_sys_platform():
    """`sys.platform` returns the cross platform."""
    assert sys.platform == EXPECTED["sys_platform"]


def test_sys_cross_compiling():
    """The environment identifies as cross-compiling."""
    assert sys.cross_compiling is True


def test_sys_multiarch():
    """The multiarch string is as expected."""
    assert sys.implementation._multiarch == EXPECTED["multiarch"]


def test_sys_abiflags():
    """The ABI flags match the cross environment."""
    assert sys.abiflags == EXPECTED["abiflags"]


def test_platform_system():
    """`platform.system()` returns the cross environment value."""
    assert platform.system() == EXPECTED["platform_system"]


def test_uname_machine():
    """`uname.machine()` returns the cross environment value."""
    assert platform.uname().machine == EXPECTED["uname_machine"]


def test_sysconfig_get_platform():
    """`sysconfig.get_platform()` returns the cross environment value."""
    assert sysconfig.get_platform() == EXPECTED["sysconfig_platform"]


def test_sysconfig_get_sysconfigdata_name():
    """The sysconfigdata name is the name for the cross environment"""
    expected_name = (
        f"_sysconfigdata_{EXPECTED['abiflags']}_"
        f"{EXPECTED['sys_platform']}_{EXPECTED['multiarch']}"
    )
    assert sysconfig._get_sysconfigdata_name() == expected_name


@pytest.mark.parametrize(
    "name",
    ["stdlib", "include", "platinclude"],
)
def test_sysconfig_get_paths_target_build(name):
    """Some `sysconfig` paths are localized to the cross environment."""
    paths = sysconfig.get_paths()
    assert paths[name].startswith(sys.base_prefix)


@pytest.mark.parametrize(
    "name",
    ["platstdlib", "purelib", "platlib", "scripts", "data"],
)
def test_sysconfig_get_paths_venv_local(name):
    """Some `sysconfig` paths are *not* localized to the cross environment."""
    paths = sysconfig.get_paths()
    assert paths[name].startswith(sys.prefix)


@pytest.mark.skipif(sys.platform != "ios", reason="iOS-specific check")
def test_platform_ios_ver():
    """iOS platform properties are as expected"""
    ios_ver = platform.ios_ver()
    assert ios_ver.release == EXPECTED["ios_release"]
    assert ios_ver.is_simulator == EXPECTED["ios_is_simulator"]
    assert ios_ver.model == EXPECTED["ios_model"]


@pytest.mark.skipif(sys.platform != "android", reason="Android-specific check")
def test_platform_android_ver():
    """Android platform properties are as expected"""
    android_ver = platform.android_ver()
    assert android_ver.release == EXPECTED["android_release"]
    assert android_ver.api_level == EXPECTED["android_api_level"]
    assert android_ver.manufacturer == EXPECTED["android_manufacturer"]
    assert android_ver.model == EXPECTED["android_model"]
    assert android_ver.device == EXPECTED["android_device"]
    assert android_ver.is_emulator == EXPECTED["android_is_emulator"]
