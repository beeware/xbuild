import os
from unittest.mock import Mock

import pytest

from xbuild.__main__ import main


@pytest.mark.parametrize(
    ("args", "error"),
    [
        pytest.param(
            (
                "--sysconfig",
                "/path/to/sysconfig.py",
                "--build-details",
                "/path/to/build-details.json",
            ),
            "not allowed with argument",
            id="sysconfig-and-build-details",
        ),
        pytest.param(
            ("--sysconfig", "/path/to/sysconfig.py", "--platform", "ios"),
            "not allowed with argument",
            id="sysconfig-and-platform",
        ),
        pytest.param(
            ("--build-details", "/path/to/build-details.json", "--platform", "android"),
            "not allowed with argument",
            id="build-details-and-platform",
        ),
        pytest.param(
            ("--sysconfig", "/path/to/sysconfig.py", "--arch", "arm64"),
            "--arch requires --platform",
            id="sysconfig-and-arch",
        ),
        pytest.param(
            ("--cache", "/path/to/cache", "--sysconfig", "/path/to/sysconfig.py"),
            "--cache requires --platform",
            id="sysconfig-and-cache",
        ),
        pytest.param(
            (
                "-C",
                "option1",
                "-C",
                "option2",
                "--config-json",
                "/path/to/config.json",
            ),
            "not allowed with argument",
            id="config-and-config-json",
        ),
        pytest.param(
            ("--cache", "/path/to/cache", "--archive", "/path/to/archive"),
            "not allowed with argument",
            id="cache-and-archive",
        ),
        pytest.param(
            ("--archive", "/path/to/archive", "--sysconfig", "/path/to/sysconfig.py"),
            "--archive requires --platform",
            id="sysconfig-and-archive",
        ),
    ],
)
def test_invalid_args(args, error, tmp_path, capsys):
    """Invalid flag combinations raise errors."""
    with pytest.raises(SystemExit) as excinfo:
        main([*args])

    assert excinfo.value.code == 2
    assert error in capsys.readouterr().err


def test_main_resolves_config_and_calls_build(tmp_path, monkeypatch):
    """main() resolves a CrossVenvConfig via resolve_cross_venv_config()
    and passes it through to _build() (regression coverage for the
    previous inline --platform resolution block, now removed in favor of
    the shared resolver)."""
    calls = {}
    fake_config = Mock()

    def fake_build(
        isolation,
        srcdir,
        outdir,
        distribution,
        config_settings,
        skip_dependency_check,
        installer,
        cross_venv_config,
    ):
        calls["cross_venv_config"] = cross_venv_config
        return "fake-wheel-0.1.0-py3-none-any.whl"

    monkeypatch.setattr(
        "xbuild.__main__.resolve_cross_venv_config",
        Mock(return_value=fake_config),
    )
    monkeypatch.setattr("xbuild.__main__.prepare_env", Mock(return_value={}))
    monkeypatch.setattr("xbuild.__main__._build", fake_build)

    main(["--platform", "ios", str(tmp_path)])

    assert calls["cross_venv_config"] is fake_config


def test_main_forwards_archive_arg_to_resolver(tmp_path, monkeypatch):
    """--archive is forwarded to resolve_cross_venv_config() as
    archive_path, alongside platform/arch/cache."""
    fake_config = Mock()
    resolve_mock = Mock(return_value=fake_config)

    monkeypatch.setattr("xbuild.__main__.resolve_cross_venv_config", resolve_mock)
    monkeypatch.setattr("xbuild.__main__.prepare_env", Mock(return_value={}))
    monkeypatch.setattr(
        "xbuild.__main__._build", Mock(return_value="fake-wheel-0.1.0-py3-none-any.whl")
    )

    main(
        [
            "--platform",
            "ios",
            "--archive",
            str(tmp_path / "my-archive"),
            str(tmp_path),
        ]
    )

    resolve_mock.assert_called_once_with(
        platform="ios",
        arch=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
        archive_path=tmp_path / "my-archive",
    )


def test_main_merges_prepare_env_into_os_environ(tmp_path, monkeypatch):
    """main() merges prepare_env()'s result into os.environ before
    calling _build()."""
    fake_config = Mock()

    monkeypatch.setattr(
        "xbuild.__main__.resolve_cross_venv_config", Mock(return_value=fake_config)
    )
    monkeypatch.setattr(
        "xbuild.__main__.prepare_env", Mock(return_value={"MY_TEST_VAR": "hello"})
    )
    monkeypatch.setattr(
        "xbuild.__main__._build", Mock(return_value="fake-wheel-0.1.0-py3-none-any.whl")
    )
    monkeypatch.delenv("MY_TEST_VAR", raising=False)

    main(["--platform", "ios", str(tmp_path)])

    assert os.environ["MY_TEST_VAR"] == "hello"
    del os.environ["MY_TEST_VAR"]


def test_main_reports_resolve_cross_venv_config_error(tmp_path, monkeypatch, capsys):
    """A ValueError from resolve_cross_venv_config() is surfaced via
    _error()/SystemExit(1), matching the existing error-handling pattern."""
    monkeypatch.setattr(
        "xbuild.__main__.resolve_cross_venv_config",
        Mock(side_effect=ValueError("boom")),
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "ios", str(tmp_path)])

    assert excinfo.value.code == 1
    assert "boom" in capsys.readouterr().err
