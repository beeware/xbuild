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
    ],
)
def test_invalid_args(args, error, tmp_path, capsys):
    """Invalid flag combinations raise errors."""
    with pytest.raises(SystemExit) as excinfo:
        main([*args])

    assert excinfo.value.code == 2
    assert error in capsys.readouterr().err


def test_platform_arg_defines_both_config_path_variables(tmp_path, monkeypatch):
    """Using --platform must not leave build_details_path or
    sysconfigdata_path completely unbound (regression test for a bug where
    only the variable matching `is_build_details` was assigned, leaving the
    other one to raise UnboundLocalError as soon as it was read while
    constructing the call to `_build`)."""
    calls = {}

    def fake_build(
        isolation,
        srcdir,
        outdir,
        distribution,
        config_settings,
        skip_dependency_check,
        installer,
        build_details_path,
        sysconfigdata_path,
    ):
        # If the bug is present, this function is never reached: the
        # UnboundLocalError happens while assembling this call's keyword
        # arguments, before `_build` itself is invoked (it gets caught by
        # `build.__main__._handle_build_error()` further up the call stack
        # and turned into a `SystemExit(1)`, without ever reaching here).
        # Reaching this function at all - with both arguments bound to some
        # value, even None - is the regression check.
        calls["build_details_path"] = build_details_path
        calls["sysconfigdata_path"] = sysconfigdata_path
        return "fake-wheel-0.1.0-py3-none-any.whl"

    monkeypatch.setattr(
        "xbuild.__main__.fetch_python",
        lambda platform_name, arch, cache_dir: (tmp_path / "build-details.json", True),
    )
    monkeypatch.setattr("xbuild.__main__.resolve_cache_dir", lambda cache_arg: tmp_path)
    monkeypatch.setattr(
        "xbuild.__main__.resolve_arch",
        lambda platform_name, arch: "arm64-iphonesimulator",
    )
    monkeypatch.setattr("xbuild.__main__._build", fake_build)

    main(["--platform", "ios", str(tmp_path)])

    assert calls["build_details_path"] == tmp_path / "build-details.json"
    assert calls["sysconfigdata_path"] is None
