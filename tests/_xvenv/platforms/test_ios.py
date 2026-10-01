import os
import sys
from unittest.mock import Mock

import pytest

from xvenv.convert import CrossVenvConfig
from xvenv.platforms.ios import (
    config_path,
    download_url,
    prepare_env,
    run_testbed,
    setup_testbed,
)

from ...utils import VersionInfo


@pytest.mark.parametrize(
    ("version_details", "arch", "url"),
    [
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://www.python.org/ftp/python/3.15.7/"
                "python-3.15.7-iOS-XCframework.tar.gz"
            ),
            id="3.15.7-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64-iphonesimulator",
            (
                "https://www.python.org/ftp/python/3.15.7/"
                "python-3.15.7-iOS-XCframework.tar.gz"
            ),
            id="3.15.7-x86_64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphoneos",
            (
                "https://www.python.org/ftp/python/3.15.7/"
                "python-3.15.7-iOS-XCframework.tar.gz"
            ),
            id="3.15.7-arm64-iphoneos",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "arm64-iphonesimulator",
            (
                "https://www.python.org/ftp/python/3.15.0/"
                "python-3.15.0rc2-iOS-XCframework.tar.gz"
            ),
            id="3.15.0rc2-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://github.com/beeware/Python-Apple-support/releases/download/"
                "3.14-b11/Python-3.14-iOS-support.b11.tar.gz"
            ),
            id="3.14.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://github.com/beeware/Python-Apple-support/releases/download/"
                "3.13-b15/Python-3.13-iOS-support.b15.tar.gz"
            ),
            id="3.13.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 12,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://github.com/beeware/Python-Apple-support/releases/download/"
                "3.12-b10/Python-3.12-iOS-support.b10.tar.gz"
            ),
            id="3.12.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 11,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "https://github.com/beeware/Python-Apple-support/releases/download/"
                "3.11-b10/Python-3.11-iOS-support.b10.tar.gz"
            ),
            id="3.11.10-arm64-iphonesimulator",
        ),
    ],
)
def test_download_url(version_details, arch, url):
    """The download URL can be constructed from the version and architecture."""
    version_info = VersionInfo(**version_details)

    actual_url = download_url(version_info, arch)

    assert actual_url == url


@pytest.mark.parametrize(
    ("version_details", "arch", "path"),
    [
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.15/build-details.json"
            ),
            id="3.15.7-x86_64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-x86_64/"
                "python3.15/build-details.json"
            ),
            id="3.15.7-x86_64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphoneos",
            "Python.xcframework/ios-arm64/lib-arm64/python3.15/build-details.json",
            id="3.15.7-arm64-iphoneos",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.15/build-details.json"
            ),
            id="3.15.0rc2-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.14/build-details.json"
            ),
            id="3.14.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.13/_sysconfigdata__ios_arm64-iphonesimulator.py"
            ),
            id="3.13.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-x86_64/"
                "python3.13/_sysconfigdata__ios_x86_64-iphonesimulator.py"
            ),
            id="3.13.10-x86_64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphoneos",
            (
                "Python.xcframework/ios-arm64/lib-arm64/"
                "python3.13/_sysconfigdata__ios_arm64-iphoneos.py"
            ),
            id="3.13.10-arm64-iphoneos",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 12,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.12/_sysconfigdata__ios_arm64-iphonesimulator.py"
            ),
            id="3.12.10-arm64-iphonesimulator",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 11,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "arm64-iphonesimulator",
            (
                "Python.xcframework/ios-arm64_x86_64-simulator/lib-arm64/"
                "python3.11/_sysconfigdata__ios_arm64-iphonesimulator.py"
            ),
            id="3.11.10-arm64-iphonesimulator",
        ),
    ],
)
def test_config_path(tmp_path, version_details, arch, path):
    """The location of the iOS configuration path can be determined."""
    version_info = VersionInfo(**version_details)

    actual_config_path = config_path(tmp_path, version_info, arch)

    assert actual_config_path == tmp_path / path


def _ios_config(arch, archive_path):
    return Mock(
        spec=CrossVenvConfig,
        platform="ios",
        arch=arch,
        archive_path=archive_path,
        build_details_path=None,
        sysconfigdata_path=archive_path / "fake-sysconfigdata.py",
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_prepare_env_simulator_slice(tmp_path, monkeypatch):
    """prepare_env() selects the simulator slice's bin/ dir for an
    -iphonesimulator arch, and replaces PATH entirely."""
    monkeypatch.setattr(
        "xvenv.platforms.ios.shutil.which", Mock(return_value="/usr/bin/xcrun")
    )
    monkeypatch.setattr(sys, "executable", "/venv/bin/python3")

    config = _ios_config("arm64-iphonesimulator", tmp_path)

    env = prepare_env(config)

    expected_slice_bin = (
        tmp_path / "Python.xcframework" / "ios-arm64_x86_64-simulator" / "bin"
    )
    assert env["PATH"] == os.pathsep.join(
        [
            "/venv/bin",
            str(expected_slice_bin),
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
            "/Library/Apple/usr/bin",
        ]
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_prepare_env_device_slice(tmp_path, monkeypatch):
    """prepare_env() selects the device slice's bin/ dir for an
    -iphoneos arch."""
    monkeypatch.setattr(
        "xvenv.platforms.ios.shutil.which", Mock(return_value="/usr/bin/xcrun")
    )
    monkeypatch.setattr(sys, "executable", "/venv/bin/python3")

    config = _ios_config("arm64-iphoneos", tmp_path)

    env = prepare_env(config)

    expected_slice_bin = tmp_path / "Python.xcframework" / "ios-arm64" / "bin"
    assert str(expected_slice_bin) in env["PATH"]


@pytest.mark.skipif(sys.platform == "darwin", reason="non-macOS-specific test")
def test_prepare_env_requires_macos(tmp_path, monkeypatch):
    """prepare_env() raises ValueError when not running on macOS."""

    config = _ios_config("arm64-iphonesimulator", tmp_path)

    with pytest.raises(ValueError, match="requires macOS"):
        prepare_env(config)


def test_prepare_env_requires_xcrun(tmp_path, monkeypatch):
    """prepare_env() raises ValueError when Xcode command-line tools
    (xcrun) are not available."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr("xvenv.platforms.ios.shutil.which", Mock(return_value=None))

    config = _ios_config("arm64-iphonesimulator", tmp_path)

    with pytest.raises(ValueError, match="Xcode command-line tools"):
        prepare_env(config)


@pytest.fixture
def mock_run(monkeypatch):
    mock = Mock()
    mock.return_value = Mock(returncode=0)
    monkeypatch.setattr("xvenv.platforms.ios.subprocess.run", mock)
    return mock


@pytest.fixture
def testbed_layout(tmp_path):
    """Simulate the directory structure run() expects to exist
    after setup_testbed(), without actually running the real testbed clone
    subprocess."""
    work_path = tmp_path / "work"
    work_path.mkdir()

    # Simulate the clone subcommand's effect by pre-creating the app/
    # and app_packages/ directories the real testbed clone would create.
    app_path = work_path / "testbed" / "iOSTestbed" / "app"
    app_packages_path = work_path / "testbed" / "iOSTestbed" / "app_packages"
    app_path.mkdir(parents=True)
    app_packages_path.mkdir(parents=True)

    return {
        "work_path": work_path,
        "app_path": app_path,
        "app_packages_path": app_packages_path,
    }


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_testbed_clone_macOS(mock_run, tmp_path):
    """The tesbed and each --src path is copied into the cloned testbed's app/
    directory."""
    archive_path = tmp_path / "archive"
    (archive_path / "testbed").mkdir(parents=True)

    work_path = tmp_path / "work"
    work_path.mkdir()
    app_path = work_path / "testbed" / "iOSTestbed" / "app"

    for path in ["tests", "deep/other"]:
        src = tmp_path / path
        src.mkdir(parents=True)
        (src / "test_thing.py").write_text("def test_x(): pass\n")

    setup_testbed(
        archive_path=archive_path,
        work_path=work_path,
        src_paths=[
            tmp_path / "tests",
            tmp_path / "deep/other",
        ],
    )

    # Clone was invoked
    clone_call = mock_run.call_args_list[0]
    args = clone_call.args[0]
    assert args[:2] == [sys.executable, str(archive_path / "testbed")]
    assert args[2] == "clone"
    assert args[3] == str(work_path / "testbed")

    # The *leaf* folders have been preserved in the final location.
    for path in ["tests", "other"]:
        copied = app_path / path / "test_thing.py"
        assert copied.is_file()
        assert copied.read_text() == "def test_x(): pass\n"


@pytest.mark.skipif(sys.platform == "darwin", reason="non-macOS-specific test")
def test_testbed_clone_non_macOS(tmp_path):
    """Testbed cloning fails on non-macOS platforms."""

    with pytest.raises(
        RuntimeError,
        match=r"Can't run an iOS project on non-macOS hardware.",
    ):
        setup_testbed(
            archive_path=tmp_path / "archive",
            work_path=tmp_path / "work",
            src_paths=[],
        )


def test_run_with_module_and_args(mock_run, testbed_layout):
    """The run subcommand is invoked with -- <module> <module_args>."""
    mock_run.return_value = Mock(returncode=3)

    result = run_testbed(
        work_path=testbed_layout["work_path"],
        args=["-m", "pytest", "tests", "-v"],
        simulator=None,
        verbose=0,
    )

    # Testbed was invoked
    mock_run.assert_called_once_with(
        [
            sys.executable,
            str(testbed_layout["work_path"] / "testbed"),
            "run",
            "--",
            "pytest",
            "tests",
            "-v",
        ],
        check=False,
    )

    # Return code of the testbed is the result
    assert result == 3


def test_args_empty(mock_run, testbed_layout):
    """An empty args list still results in a bare trailing --."""
    run_testbed(
        work_path=testbed_layout["work_path"],
        args=[],
        simulator=None,
        verbose=0,
    )

    mock_run.assert_called_once_with(
        [
            sys.executable,
            str(testbed_layout["work_path"] / "testbed"),
            "run",
            "--",
        ],
        check=False,
    )


def test_forwards_simulator_flag(mock_run, testbed_layout):
    """--simulator is forwarded to the run subcommand."""
    run_testbed(
        work_path=testbed_layout["work_path"],
        args=["-m", "pytest"],
        simulator="iPhone 16e",
        verbose=0,
    )

    mock_run.assert_called_once_with(
        [
            sys.executable,
            str(testbed_layout["work_path"] / "testbed"),
            "run",
            "--simulator",
            "iPhone 16e",
            "--",
            "pytest",
        ],
        check=False,
    )


def test_forwards_verbose_flag(mock_run, testbed_layout, tmp_path):
    """verbose > 0 adds -v to the run subcommand."""
    run_testbed(
        work_path=testbed_layout["work_path"],
        args=["-m", "pytest"],
        simulator=None,
        verbose=1,
    )

    mock_run.assert_called_once_with(
        [
            sys.executable,
            str(testbed_layout["work_path"] / "testbed"),
            "run",
            "-v",
            "--",
            "pytest",
        ],
        check=False,
    )


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["-m"], id="missing-module"),
        pytest.param(["-c", "print('hello')"], id="inline"),
        pytest.param(["hello.py"], id="script"),
    ],
)
def test_bad_args(mock_run, testbed_layout, args):
    """Unsupported arguments to run() raise a ValueError."""

    with pytest.raises(
        ValueError, match="iOS requires -m <module> as the first two arguments after --"
    ):
        run_testbed(
            work_path=testbed_layout["work_path"],
            args=args,
            simulator=None,
            verbose=0,
        )

    # Run wasn't called.
    mock_run.assert_not_called()
