from unittest import mock

import pytest

from xvenv.__main__ import main


def test_platform_and_sysconfig_together_is_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--platform",
                "ios",
                "--sysconfig",
                str(tmp_path / "fake.py"),
                str(tmp_path / "x-venv"),
            ]
        )

    assert excinfo.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_platform_and_build_details_together_is_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--platform",
                "android",
                "--build-details",
                str(tmp_path / "fake.json"),
                str(tmp_path / "x-venv"),
            ]
        )

    assert excinfo.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_arch_without_platform_is_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--sysconfig",
                str(tmp_path / "fake.py"),
                "--arch",
                "aarch64",
                str(tmp_path / "x-venv"),
            ]
        )

    assert excinfo.value.code == 2
    assert "--arch requires --platform" in capsys.readouterr().err


def test_cache_without_platform_is_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--sysconfig",
                str(tmp_path / "fake.py"),
                "--cache",
                str(tmp_path / "cache"),
                str(tmp_path / "x-venv"),
            ]
        )

    assert excinfo.value.code == 2
    assert "--cache requires --platform" in capsys.readouterr().err


def test_platform_calls_fetch_and_convert(tmp_path):
    venv_path = tmp_path / "x-venv"
    cache_path = tmp_path / "cache"
    fake_config_path = tmp_path / "fake-build-details.json"

    with (
        mock.patch("xvenv.__main__.venv.create") as venv_create,
        mock.patch(
            "xvenv.__main__.resolve_cache_dir", return_value=cache_path
        ) as resolve_cache_dir,
        mock.patch(
            "xvenv.__main__.fetch_python",
            return_value=(fake_config_path, True),
        ) as fetch_python,
        mock.patch(
            "xvenv.__main__.convert_venv", return_value="android aarch64"
        ) as convert_venv,
    ):
        main(
            [
                "--platform",
                "android",
                "--arch",
                "aarch64",
                "--cache",
                str(cache_path),
                str(venv_path),
            ]
        )

    venv_create.assert_called_once_with(venv_path, with_pip=True)
    resolve_cache_dir.assert_called_once_with(cache_path)
    fetch_python.assert_called_once_with("android", "aarch64", cache_path)
    convert_venv.assert_called_once_with(
        venv_path,
        build_details_path=fake_config_path,
        sysconfigdata_path=None,
    )


def test_platform_with_sysconfigdata_result_passes_sysconfigdata_path(tmp_path):
    venv_path = tmp_path / "x-venv"
    fake_config_path = tmp_path / "fake-sysconfigdata.py"

    with (
        mock.patch("xvenv.__main__.venv.create"),
        mock.patch("xvenv.__main__.resolve_cache_dir", return_value=tmp_path / "cache"),
        mock.patch(
            "xvenv.__main__.fetch_python",
            return_value=(fake_config_path, False),
        ),
        mock.patch(
            "xvenv.__main__.convert_venv", return_value="ios arm64-iphonesimulator"
        ) as convert_venv,
    ):
        main(["--platform", "ios", str(venv_path)])

    convert_venv.assert_called_once_with(
        venv_path,
        build_details_path=None,
        sysconfigdata_path=fake_config_path,
    )


def test_platform_emscripten_not_implemented_error_is_reported(tmp_path, capsys):
    venv_path = tmp_path / "x-venv"

    with (
        mock.patch("xvenv.__main__.venv.create"),
        mock.patch("xvenv.__main__.resolve_cache_dir", return_value=tmp_path / "cache"),
        mock.patch(
            "xvenv.__main__.fetch_python",
            side_effect=NotImplementedError("no emscripten yet"),
        ),
        pytest.raises(SystemExit) as excinfo,
    ):
        main(["--platform", "emscripten", str(venv_path)])

    assert excinfo.value.code == 1
    assert "no emscripten yet" in capsys.readouterr().err
