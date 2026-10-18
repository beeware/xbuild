import shlex
import sys
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from xvenv.convert import CrossVenvConfig
from xvenv.fetch import parse_sysconfigdata
from xvenv.platforms.android import (
    TESTBED_RESOURCES,
    android_sysconfigdata,
    config_path,
    download_url,
    fetch_archive,
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
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            (
                "https://www.python.org/ftp/python/3.14.7/"
                "python-3.14.7-aarch64-linux-android.tar.gz"
            ),
            id="3.14.7-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            (
                "https://www.python.org/ftp/python/3.14.7/"
                "python-3.14.7-x86_64-linux-android.tar.gz"
            ),
            id="3.14.7-x86_64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "aarch64",
            (
                "https://www.python.org/ftp/python/3.15.0/"
                "python-3.15.0rc2-aarch64-linux-android.tar.gz"
            ),
            id="3.15.0rc2-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            (
                "https://repo.maven.apache.org/maven2/com/chaquo/python/python/"
                "3.13.15/python-3.13.15-aarch64-linux-android.tar.gz"
            ),
            id="3.13.11-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            (
                "https://repo.maven.apache.org/maven2/com/chaquo/python/python/"
                "3.13.15/python-3.13.15-x86_64-linux-android.tar.gz"
            ),
            id="3.13.11-x86_64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 12,
                "micro": 4,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            (
                "https://repo.maven.apache.org/maven2/com/chaquo/python/target/"
                "3.12.15-0/target-3.12.15-0-arm64-v8a.zip"
            ),
            id="3.12.4-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 12,
                "micro": 4,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            (
                "https://repo.maven.apache.org/maven2/com/chaquo/python/target/"
                "3.12.15-0/target-3.12.15-0-x86_64.zip"
            ),
            id="3.12.4-x86_64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 11,
                "micro": 9,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            (
                "https://repo.maven.apache.org/maven2/com/chaquo/python/target/"
                "3.11.17-0/target-3.11.17-0-arm64-v8a.zip"
            ),
            id="3.11.9-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 11,
                "micro": 9,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            (
                "https://repo.maven.apache.org/maven2/com/chaquo/python/target/"
                "3.11.17-0/target-3.11.17-0-x86_64.zip"
            ),
            id="3.11.9-x86_64",
        ),
    ],
)
def test_download_url(version_details, arch, url):
    """The download URL can be constructed from the version and architecture."""
    version_info = VersionInfo(**version_details)

    actual_url = download_url(version_info, arch)

    assert actual_url == url


def test_download_url_unsupported_version():
    """Python versions older than 3.11 aren't supported."""
    version_info = VersionInfo(
        major=3, minor=10, micro=14, releaselevel="final", serial=0
    )

    with pytest.raises(ValueError, match=r"doesn't support Python 3.10 on Android"):
        download_url(version_info, "aarch64")


@pytest.mark.parametrize(
    ("version_details", "arch", "path"),
    [
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            "prefix/lib/python3.14/build-details.json",
            id="3.14.7-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            "prefix/lib/python3.14/build-details.json",
            id="3.14.7-x86_64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 15,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "aarch64",
            "prefix/lib/python3.15/build-details.json",
            id="3.15.0rc2-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            "prefix/lib/python3.13/_sysconfigdata__android_aarch64-linux-android.py",
            id="3.13.10-aarch64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "x86_64",
            "prefix/lib/python3.13/_sysconfigdata__android_x86_64-linux-android.py",
            id="3.13.10-x86_64",
        ),
        pytest.param(
            {
                "major": 3,
                "minor": 12,
                "micro": 4,
                "releaselevel": "final",
                "serial": 0,
            },
            "aarch64",
            "prefix/lib/python3.12/_sysconfigdata__android_aarch64-linux-android.py",
            id="3.12.4-aarch64",
        ),
    ],
)
def test_config_path(tmp_path, version_details, arch, path):
    """The location of the Android configuration path can be determined."""
    version_info = VersionInfo(**version_details)

    actual_config_path = config_path(tmp_path, version_info, arch)

    assert actual_config_path == tmp_path / path


# A subset of the sysconfigdata of a Chaquopy build, generated on x86_64.
CHAQUOPY_NDK_BIN = (
    "/Users/brutus/Library/Android/sdk/ndk/27.3.13750724/"
    "toolchains/llvm/prebuilt/darwin-x86_64/bin"
)
CHAQUOPY_BUILD_TIME_VARS = {
    "ANDROID_API_LEVEL": 24,
    "CC": f"{CHAQUOPY_NDK_BIN}/x86_64-linux-android24-clang",
    "HOST_GNU_TYPE": "x86_64-pc-linux-android",
    "LDFLAGS": "-L/sysroot/usr/lib/x86_64-linux-android/24",
    "MULTIARCH": "",
    "Py_ENABLE_SHARED": 1,
    "VERSION": "3.12",
    "prefix": "/usr/local",
}


def _make_zip(path, files):
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


@pytest.fixture
def chaquopy_downloads(tmp_path):
    """Fake Chaquopy 3.12 zip files, keyed by download URL."""
    downloads_path = tmp_path / "downloads"
    downloads_path.mkdir()

    abi_zip = downloads_path / "abi.zip"
    _make_zip(
        abi_zip,
        {
            "include/python3.12/Python.h": "/* Python.h */\n",
            "include/openssl/ssl.h": "/* ssl.h */\n",
            "jniLibs/arm64-v8a/libpython3.12.so": "libpython",
            "jniLibs/arm64-v8a/libssl_python.so": "libssl",
            "lib-dynload/arm64-v8a/_ssl.cpython-312.so": "_ssl",
        },
    )
    stdlib_zip = downloads_path / "stdlib.zip"
    _make_zip(
        stdlib_zip,
        {
            "os.py": "# os module\n",
            "_sysconfigdata__linux_.py": (
                f"build_time_vars = {CHAQUOPY_BUILD_TIME_VARS!r}\n"
            ),
        },
    )

    base_url = "https://repo.maven.apache.org/maven2/com/chaquo/python/target/"
    return {
        f"{base_url}3.12.15-0/target-3.12.15-0-arm64-v8a.zip": abi_zip,
        f"{base_url}3.12.15-0/target-3.12.15-0-stdlib.zip": stdlib_zip,
    }


@pytest.fixture
def mock_urlretrieve(monkeypatch, chaquopy_downloads):
    def fake_urlretrieve(url, filename):
        Path(filename).write_bytes(chaquopy_downloads[url].read_bytes())

    urlretrieve = Mock(side_effect=fake_urlretrieve)
    monkeypatch.setattr("urllib.request.urlretrieve", urlretrieve)
    return urlretrieve


VERSION_3_12 = VersionInfo(major=3, minor=12, micro=4, releaselevel="final", serial=0)


def test_fetch_archive_chaquopy(tmp_path, mock_urlretrieve, chaquopy_downloads):
    """A Python 3.12 build is assembled from Chaquopy's zip files into the
    layout of an official Android release package."""
    cache_path = tmp_path / "cache"
    cache_path.mkdir()

    archive_path = fetch_archive(VERSION_3_12, "aarch64", cache_path)

    assert archive_path == cache_path / "chaquopy-3.12.15-0-aarch64-linux-android"
    assert sorted(call.args[0] for call in mock_urlretrieve.call_args_list) == sorted(
        chaquopy_downloads
    )

    # Headers, shared libraries and the standard library are in the prefix.
    prefix_path = archive_path / "prefix"
    assert (prefix_path / "include" / "python3.12" / "Python.h").is_file()
    assert (prefix_path / "include" / "openssl" / "ssl.h").is_file()
    assert (prefix_path / "lib" / "libpython3.12.so").is_file()
    assert (prefix_path / "lib" / "libssl_python.so").is_file()
    stdlib_path = prefix_path / "lib" / "python3.12"
    assert (stdlib_path / "os.py").is_file()
    assert (stdlib_path / "lib-dynload" / "_ssl.cpython-312.so").is_file()
    assert not (prefix_path / "jniLibs").exists()
    assert not (prefix_path / "lib-dynload").exists()

    # The sysconfigdata module of an official build has been generated, for the
    # requested architecture.
    config_file = config_path(archive_path, VERSION_3_12, "aarch64")
    assert config_file.is_file()
    build_time_vars = parse_sysconfigdata(config_file).build_time_vars
    assert build_time_vars["MULTIARCH"] == "aarch64-linux-android"
    assert build_time_vars["HOST_GNU_TYPE"] == "aarch64-unknown-linux-android"
    assert build_time_vars["CC"] == f"{CHAQUOPY_NDK_BIN}/aarch64-linux-android24-clang"
    assert build_time_vars["ANDROID_API_LEVEL"] == 24

    # The build tools of an official build have been added, using the API level
    # of the Chaquopy build.
    assert (archive_path / "android.py").read_text() == (
        TESTBED_RESOURCES / "android.py"
    ).read_text()
    env_script = (archive_path / "android-env.sh").read_bytes()
    assert b'ANDROID_API_LEVEL:=24}"' in env_script
    assert b"\r\n" not in env_script

    # Nothing is left behind from the assembly process.
    assert sorted(path.name for path in cache_path.iterdir() if path.is_dir()) == [
        "chaquopy-3.12.15-0-aarch64-linux-android"
    ]


def test_fetch_archive_chaquopy_cached(tmp_path, mock_urlretrieve):
    """An already-assembled Chaquopy build is reused."""
    cache_path = tmp_path / "cache"
    cache_path.mkdir()
    fetch_archive(VERSION_3_12, "aarch64", cache_path)
    mock_urlretrieve.reset_mock()

    archive_path = fetch_archive(VERSION_3_12, "aarch64", cache_path)

    assert archive_path == cache_path / "chaquopy-3.12.15-0-aarch64-linux-android"
    mock_urlretrieve.assert_not_called()


def test_fetch_archive_chaquopy_failure(tmp_path, monkeypatch, mock_urlretrieve):
    """If the Chaquopy build can't be assembled, no partial archive is left in
    the cache."""
    resources_path = tmp_path / "resources"
    resources_path.mkdir()
    (resources_path / "android-env.sh").write_text("# No API level\n")
    monkeypatch.setattr(
        "xvenv.platforms.android.TESTBED_RESOURCES",
        resources_path,
    )
    cache_path = tmp_path / "cache"
    cache_path.mkdir()

    with pytest.raises(ValueError, match=r"Unable to set the API level"):
        fetch_archive(VERSION_3_12, "aarch64", cache_path)

    assert [path for path in cache_path.iterdir() if path.is_dir()] == []


@pytest.mark.parametrize(
    ("arch", "cc", "ldflags", "host_gnu_type"),
    [
        pytest.param(
            "aarch64",
            f"{CHAQUOPY_NDK_BIN}/aarch64-linux-android24-clang",
            "-L/sysroot/usr/lib/aarch64-linux-android/24",
            "aarch64-unknown-linux-android",
            id="aarch64",
        ),
        pytest.param(
            "x86_64",
            f"{CHAQUOPY_NDK_BIN}/x86_64-linux-android24-clang",
            "-L/sysroot/usr/lib/x86_64-linux-android/24",
            "x86_64-pc-linux-android",
            id="x86_64",
        ),
    ],
)
def test_android_sysconfigdata(arch, cc, ldflags, host_gnu_type):
    """Chaquopy's sysconfig data is converted to describe the requested
    architecture, without altering references to the build machine."""
    android_vars = android_sysconfigdata(CHAQUOPY_BUILD_TIME_VARS, arch)

    assert android_vars == {
        **CHAQUOPY_BUILD_TIME_VARS,
        "CC": cc,
        "HOST_GNU_TYPE": host_gnu_type,
        "LDFLAGS": ldflags,
        "MULTIARCH": f"{arch}-linux-android",
    }


def _write_fake_android_py(
    archive_path: Path,
    env_vars: dict[str, str] | None = None,
    exit_code: int = 0,
    stdout: str | None = None,
    stderr: str = "",
) -> None:
    """Write a fake `android.py` script to `archive_path`, standing in for
    the real cpython-source-deps `android.py` script that `prepare_env()`
    invokes (`android.py env`). This lets tests exercise prepare_env()'s
    own subprocess-invocation/output-parsing logic without needing a real
    NDK/toolchain installation.

    :param env_vars: If given, the fake `env` subcommand prints
        `export KEY=VALUE` for each item (values are shell-quoted via
        `shlex.quote`, matching the real script's `print_env()`), exits 0,
        and `stdout`/`exit_code` are ignored.
    :param stdout: Raw stdout to print verbatim instead of `env_vars`
        (used to test malformed-output handling).
    :param exit_code: Exit code when `env_vars` is not given.
    :param stderr: Stderr text to print when `env_vars` is not given.
    """
    if env_vars is not None:
        lines = "\n".join(
            f"print({f'export {key}={shlex.quote(value)}'!r})"
            for key, value in env_vars.items()
        )
        body = f"{lines}\n"
    else:
        stdout_repr = repr(stdout or "")
        stderr_repr = repr(stderr)
        body = (
            "import sys\n"
            f"sys.stdout.write({stdout_repr})\n"
            f"sys.stderr.write({stderr_repr})\n"
            f"sys.exit({exit_code})\n"
        )

    (archive_path / "android.py").write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "assert sys.argv[1:] == ['env'], sys.argv\n"
        f"{body}\n"
    )


def _android_config(
    archive_path,
    sysconfigdata_path=None,
    build_details_path=None,
    arch="aarch64-linux-android",
):
    return Mock(
        spec=CrossVenvConfig,
        platform="android",
        arch=arch,
        archive_path=archive_path,
        build_details_path=build_details_path,
        sysconfigdata_path=sysconfigdata_path,
    )


def test_prepare_env_success(tmp_path, monkeypatch):
    """prepare_env() runs the archive's android.py env subcommand and
    parses its `export KEY=VALUE` output into a dict, including values
    containing spaces (quoted by the real script's print_env())."""
    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "android-sdk"))

    _write_fake_android_py(
        archive_path,
        env_vars={
            "CC": "/ndk/bin/aarch64-linux-android24-clang",
            "CFLAGS": "-D__BIONIC_NO_PAGE_SIZE_MACRO -I/archive/prefix/include",
            "CPU_COUNT": "8",
        },
    )

    config = _android_config(archive_path)

    env = prepare_env(config)

    assert env == {
        "CC": "/ndk/bin/aarch64-linux-android24-clang",
        "CFLAGS": "-D__BIONIC_NO_PAGE_SIZE_MACRO -I/archive/prefix/include",
        "CPU_COUNT": "8",
    }


def test_prepare_env_missing_android_home(tmp_path, monkeypatch):
    """ANDROID_HOME not set raises a clear ValueError, without even
    checking for android.py's existence."""
    monkeypatch.delenv("ANDROID_HOME", raising=False)

    config = _android_config(tmp_path)

    with pytest.raises(ValueError, match="ANDROID_HOME"):
        prepare_env(config)


def test_prepare_env_missing_android_py(tmp_path, monkeypatch):
    """A missing android.py in the archive raises a clear ValueError."""
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "android-sdk"))

    config = _android_config(tmp_path / "archive")

    with pytest.raises(ValueError, match="Could not find"):
        prepare_env(config)


def test_prepare_env_subprocess_failure(tmp_path, monkeypatch):
    """If `android.py env` exits non-zero an error is raised."""
    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "android-sdk"))

    _write_fake_android_py(
        archive_path,
        exit_code=1,
        stderr="/ndk/bin/some-tool does not exist\n",
    )

    config = _android_config(archive_path)

    with pytest.raises(ValueError, match="some-tool does not exist"):
        prepare_env(config)


@pytest.mark.parametrize(
    "stdout",
    [
        "not-export FOO=bar\n",
        "export FOO\n",
    ],
)
def test_prepare_env_malformed_output(tmp_path, monkeypatch, stdout):
    """Unexpected output from `android.py env` raises a clear ValueError."""
    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "android-sdk"))

    _write_fake_android_py(archive_path, stdout=stdout)

    config = _android_config(archive_path)

    with pytest.raises(ValueError, match="Unexpected output"):
        prepare_env(config)


def test_prepare_env_disables_cross_env(tmp_path, monkeypatch):
    """android.py env is run with cross env patches disabled, so it works
    from inside an Android cross env."""
    archive_path = tmp_path / "archive"
    archive_path.mkdir()
    (archive_path / "android.py").write_text("")
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path / "android-sdk"))
    run = Mock(return_value=Mock(stdout=""))
    monkeypatch.setattr("xvenv.platforms.android.subprocess.run", run)

    prepare_env(_android_config(archive_path))

    assert run.call_args.kwargs["env"]["XBUILD_ENV"] == "off"


@pytest.fixture
def mock_run(monkeypatch):
    mock = Mock()
    mock.return_value = Mock(returncode=0)
    monkeypatch.setattr("xvenv.platforms.android.subprocess.run", mock)
    return mock


@pytest.fixture
def work_path(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    return work


def _testbed_archive(tmp_path, series, android_support):
    """A fake Android archive, containing a standard library for `series`
    (with an `_android_support` module, if `android_support` is true)."""
    archive_path = tmp_path / "archive"
    stdlib_path = archive_path / "prefix" / "lib" / f"python{series}"
    stdlib_path.mkdir(parents=True)
    (stdlib_path / "os.py").write_text("# os module\n")
    if android_support:
        (stdlib_path / "_android_support.py").write_text("# android support\n")
    (archive_path / "android-env.sh").write_text("# env script\n")

    # The archive's own testbed shouldn't be used.
    (archive_path / "android.py").write_text("# archive driver\n")
    (archive_path / "testbed").mkdir()
    (archive_path / "testbed" / "build.gradle").write_text("# archive testbed\n")

    return archive_path


def test_testbed_clone(monkeypatch, tmp_path):
    """xpython's copy of the testbed is cloned, and each --src path is copied
    into work_path/src."""
    # Monkeypatch so that it looks like we're not in CI
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    archive_path = _testbed_archive(tmp_path, "3.14", android_support=True)

    for path in ["tests", "deep/other"]:
        src = tmp_path / path
        src.mkdir(parents=True)
        (src / "test_thing.py").write_text("def test_x(): pass\n")

    work_path = tmp_path / "work"

    setup_testbed(
        archive_path=archive_path,
        work_path=work_path,
        src_paths=[
            tmp_path / "tests",
            tmp_path / "deep/other",
        ],
    )

    # xpython's copy of the testbed was cloned, not the archive's copy.
    copied = work_path / "android.py"
    assert copied.is_file()
    assert copied.read_text() == (TESTBED_RESOURCES / "android.py").read_text()

    assert (work_path / "testbed" / "app" / "build.gradle.kts").is_file()
    assert not (work_path / "testbed" / "build.gradle").exists()

    # The archive's Python and build configuration are linked into the testbed.
    assert (work_path / "prefix").resolve() == (archive_path / "prefix").resolve()
    assert (work_path / "android-env.sh").read_text() == "# env script\n"

    # Python 3.13+ redirects its own output to the Android log.
    assert not (work_path / "testbed" / "app" / "src" / "main" / "python").exists()

    # The *leaf* folders have been preserved in the final location.
    for path in ["tests", "other"]:
        copied = work_path / "src" / path / "test_thing.py"
        assert copied.is_file()
        assert copied.read_text() == "def test_x(): pass\n"


def test_testbed_clone_legacy_streams(monkeypatch, tmp_path):
    """If the target Python doesn't redirect its own output to the Android log,
    a backport of the redirection is added to the testbed's site-packages."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    archive_path = _testbed_archive(tmp_path, "3.12", android_support=False)
    work_path = tmp_path / "work"

    setup_testbed(archive_path=archive_path, work_path=work_path, src_paths=[])

    python_path = work_path / "testbed" / "app" / "src" / "main" / "python"
    assert sorted(path.name for path in python_path.iterdir()) == [
        "_android_support.py",
        "_xpython_logcat.pth",
        "_xpython_logcat.py",
    ]
    assert (python_path / "_xpython_logcat.pth").read_text() == (
        "import _xpython_logcat\n"
    )


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS specific test")
def test_testbed_clone_macOS_ci(monkeypatch, tmp_path):
    """If running on GitHub Actions under macOS, an error is raised on clone."""
    # Monkeypatch so that it looks like we're in CI, regardless of whether we are.
    monkeypatch.setenv("GITHUB_ACTIONS", "1")

    with pytest.raises(
        RuntimeError,
        match=r"GitHub Actions can't start an Android emulator on a macOS runner.",
    ):
        setup_testbed(
            archive_path=tmp_path / "archive",
            work_path=tmp_path / "work",
            src_paths=[],
        )


def test_testbed_clone_macOS_ci_in_cross_env(monkeypatch, tmp_path):
    """The macOS CI check uses the host platform, not the patched
    sys.platform."""
    monkeypatch.setenv("GITHUB_ACTIONS", "1")
    monkeypatch.setattr(sys, "platform", "android")
    monkeypatch.setattr(sys, "_host_platform", "darwin", raising=False)

    with pytest.raises(
        RuntimeError,
        match=r"GitHub Actions can't start an Android emulator on a macOS runner.",
    ):
        setup_testbed(
            archive_path=tmp_path / "archive",
            work_path=tmp_path / "work",
            src_paths=[],
        )


def test_run_with_module_and_args(mock_run, work_path):
    """The run subcommand is invoked with -- <module> <module_args>."""
    mock_run.return_value = Mock(returncode=3)

    result = run_testbed(
        work_path=work_path,
        args=["-m", "pytest", "tests", "-v"],
        managed=None,
        connected=None,
        verbose=0,
    )

    # Testbed was invoked
    args = mock_run.call_args.args[0]
    assert args[0] == sys.executable
    assert args[1] == str(work_path / "android.py")
    assert args[2] == "test"
    assert "--site-packages" in args
    assert args[args.index("--site-packages") + 1] == str(work_path / "site-packages")
    assert "--cwd" in args
    assert args[args.index("--cwd") + 1] == str(work_path / "src")
    assert "--managed" in args
    assert args[args.index("--managed") + 1] == "maxVersion"
    assert "--connected" not in args
    assert args[-5:] == ["--", "-m", "pytest", "tests", "-v"]
    assert mock_run.call_args.kwargs["env"]["XBUILD_ENV"] == "off"

    # Return code of the testbed is the result
    assert result == 3


def test_args_dash_c(mock_run, work_path):
    """args starting with -c (not -m) are passed through
    verbatim, with no xpython-side validation or forced -m."""
    run_testbed(
        work_path=work_path,
        args=["-c", "print(1)"],
        managed=None,
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[-3:] == ["--", "-c", "print(1)"]


def test_args_empty(mock_run, work_path):
    """An empty args list still results in a bare trailing --."""
    run_testbed(
        work_path=work_path,
        args=[],
        managed=None,
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[-1] == "--"


def test_forwards_managed_flag(mock_run, work_path):
    """An explicit --managed overrides the default."""
    run_testbed(
        work_path=work_path,
        args=["-m", "pytest"],
        managed="minVersion",
        connected=None,
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert args[args.index("--managed") + 1] == "minVersion"


def test_forwards_connected_flag(mock_run, work_path):
    """--connected is forwarded instead of --managed when given."""
    run_testbed(
        work_path=work_path,
        args=["-m", "pytest"],
        managed=None,
        connected="emulator-5554",
        verbose=0,
    )

    args = mock_run.call_args.args[0]
    assert "--managed" not in args
    assert "--connected" in args
    assert args[args.index("--connected") + 1] == "emulator-5554"


def test_forwards_verbose_flag(mock_run, work_path):
    """verbose > 0 adds -v to the invocation."""
    run_testbed(
        work_path=work_path,
        args=["-m", "pytest"],
        managed=None,
        connected=None,
        verbose=1,
    )

    args = mock_run.call_args.args[0]
    assert "-v" in args
