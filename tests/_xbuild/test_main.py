import os
import sys
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
            "--arch option also requires --platform",
            id="sysconfig-and-arch",
        ),
        pytest.param(
            ("--cache", "/path/to/cache", "--sysconfig", "/path/to/sysconfig.py"),
            "--cache option also requires --platform",
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
            "--archive option also requires --platform",
            id="sysconfig-and-archive",
        ),
    ],
)
def test_invalid_args(args, error, capsys):
    """Invalid flag combinations raise errors."""
    with pytest.raises(SystemExit) as excinfo:
        main([*args])

    assert excinfo.value.code == 2
    assert error in capsys.readouterr().err


def test_main_resolves_config_and_calls_build(tmp_path, monkeypatch):
    """main() resolves a CrossVenvConfig and passes it through to _build()."""
    calls = {}
    mock_config = Mock()

    def mock_build(
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

    mock_config = Mock()
    mock_config.prepare_env = Mock(return_value={"MY_TEST_VAR": "hello"})
    mock_CrossVenvConfig = Mock(return_value=mock_config)

    monkeypatch.setattr("xbuild.__main__.CrossVenvConfig", mock_CrossVenvConfig)
    monkeypatch.setattr("xbuild.__main__._build", mock_build)

    main(["--platform", "ios", str(tmp_path)])

    assert calls["cross_venv_config"] is mock_config


def test_main_forwards_archive_arg_to_resolver(tmp_path, monkeypatch):
    """A cross environment can be created pointing at an existing archive."""
    mock_config = Mock()
    mock_config.prepare_env = Mock(return_value={"MY_TEST_VAR": "hello"})
    mock_CrossVenvConfig = Mock(return_value=mock_config)

    monkeypatch.setattr("xbuild.__main__.CrossVenvConfig", mock_CrossVenvConfig)
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

    mock_CrossVenvConfig.assert_called_once_with(
        platform="ios",
        arch=None,
        archive_path=tmp_path / "my-archive",
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )


def test_main_merges_prepare_env_into_os_environ(tmp_path, monkeypatch):
    """xbuild merges platform environment details into the running environment."""
    mock_config = Mock()
    mock_config.prepare_env = Mock(return_value={"MY_TEST_VAR": "hello"})

    monkeypatch.setattr(
        "xbuild.__main__.CrossVenvConfig", Mock(return_value=mock_config)
    )
    monkeypatch.setattr(
        "xbuild.__main__._build", Mock(return_value="fake-wheel-0.1.0-py3-none-any.whl")
    )
    monkeypatch.delenv("MY_TEST_VAR", raising=False)

    main(["--platform", "ios", str(tmp_path)])

    assert os.environ["MY_TEST_VAR"] == "hello"


def test_main_reports_config_error(tmp_path, monkeypatch, capsys):
    """An error when configuring the environment is surfaced."""
    monkeypatch.setattr(
        "xbuild.__main__.CrossVenvConfig",
        Mock(side_effect=ValueError("boom")),
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["--platform", "ios", str(tmp_path)])

    assert excinfo.value.code == 1
    assert "boom" in capsys.readouterr().err


@pytest.fixture
def mock_CrossVenvConfig(monkeypatch):
    mock_config = Mock()
    mock_config.prepare_env = Mock(return_value={})
    CrossVenvConfig = Mock(return_value=mock_config)
    CrossVenvConfig.from_current_env.return_value = mock_config
    monkeypatch.setattr("xbuild.__main__.CrossVenvConfig", CrossVenvConfig)
    return CrossVenvConfig


@pytest.fixture
def mock_build(monkeypatch):
    build = Mock(return_value="fake-wheel-0.1.0-py3-none-any.whl")
    monkeypatch.setattr("xbuild.__main__._build", build)
    return build


def test_no_config_outside_cross_env(monkeypatch, tmp_path, capsys):
    """Outside a cross env, a configuration source is required."""
    monkeypatch.delattr(sys, "cross_compiling", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        main([str(tmp_path)])

    assert excinfo.value.code == 2
    assert (
        "One of the arguments --build-details, --sysconfig, or --platform is required"
        in capsys.readouterr().err
    )


def test_no_config_in_cross_env(
    monkeypatch, tmp_path, mock_CrossVenvConfig, mock_build
):
    """Inside a cross env, the current environment's config is used if no
    configuration source is given."""
    monkeypatch.setattr(sys, "cross_compiling", True, raising=False)

    main([str(tmp_path)])

    mock_CrossVenvConfig.assert_not_called()
    mock_CrossVenvConfig.from_current_env.assert_called_once_with()
    current_config = mock_CrossVenvConfig.from_current_env.return_value
    current_config.prepare_env.assert_called_once_with()
    # The resolved config is the last positional argument to _build()
    assert mock_build.call_args.args[-1] is current_config


def test_explicit_config_in_cross_env(
    monkeypatch, tmp_path, mock_CrossVenvConfig, mock_build
):
    """Inside a cross env, an explicit configuration source takes precedence."""
    monkeypatch.setattr(sys, "cross_compiling", True, raising=False)

    main(["--platform", "ios", str(tmp_path)])

    mock_CrossVenvConfig.from_current_env.assert_not_called()
    mock_CrossVenvConfig.assert_called_once_with(
        platform="ios",
        arch=None,
        archive_path=None,
        build_details_path=None,
        sysconfigdata_path=None,
        cache_path=None,
    )


def test_current_env_error(monkeypatch, tmp_path, mock_CrossVenvConfig, capsys):
    """An error determining the current env's configuration is surfaced."""
    monkeypatch.setattr(sys, "cross_compiling", True, raising=False)
    mock_CrossVenvConfig.from_current_env.side_effect = ValueError("no record")

    with pytest.raises(SystemExit) as excinfo:
        main([str(tmp_path)])

    assert excinfo.value.code == 1
    assert "no record" in capsys.readouterr().err
