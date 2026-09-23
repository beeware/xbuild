from unittest.mock import Mock

import pytest

from xpython.deps import install_requirements, resolve_requirements


def test_resolve_only_dependencies(tmp_path):
    """--dependency specs pass through unchanged when no groups are given."""
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text("[dependency-groups]\n")

    result = resolve_requirements(["requests", "attrs>=23"], [], pyproject_path)

    assert result == ["requests", "attrs>=23"]


def test_resolve_only_groups(tmp_path):
    """--group names expand via PEP 735 resolution against pyproject.toml."""
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[dependency-groups]\ntest = ["pytest", "pytest-cov"]\n')

    result = resolve_requirements([], ["test"], pyproject_path)

    assert result == ["pytest", "pytest-cov"]


def test_resolve_groups_and_dependencies_merged(tmp_path):
    """--group expansions and --dependency specs are merged, groups first."""
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[dependency-groups]\ntest = ["pytest"]\n')

    result = resolve_requirements(["requests"], ["test"], pyproject_path)

    assert result == ["pytest", "requests"]


def test_resolve_multiple_groups(tmp_path):
    """Multiple --group names are all expanded and merged in order."""
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        '[dependency-groups]\ntest = ["pytest"]\nlint = ["ruff"]\n'
    )

    result = resolve_requirements([], ["test", "lint"], pyproject_path)

    assert result == ["pytest", "ruff"]


def test_resolve_unknown_group_raises(tmp_path):
    """An unknown group name raises ValueError with a clear message."""
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[dependency-groups]\ntest = ["pytest"]\n')

    with pytest.raises(ValueError, match="missing"):
        resolve_requirements([], ["missing"], pyproject_path)


def test_resolve_missing_pyproject_raises(tmp_path):
    """A missing pyproject.toml raises ValueError with a clear message."""
    pyproject_path = tmp_path / "does-not-exist.toml"

    with pytest.raises(ValueError, match="does-not-exist.toml"):
        resolve_requirements([], ["test"], pyproject_path)


def test_resolve_no_groups_needed_without_pyproject(tmp_path):
    """If no --group names are given, a missing pyproject.toml is fine."""
    pyproject_path = tmp_path / "does-not-exist.toml"

    result = resolve_requirements(["requests"], [], pyproject_path)

    assert result == ["requests"]


def test_install_requirements_runs_pip(tmp_path, monkeypatch):
    """install_requirements() invokes pip install --target with the given
    requirements and --find-links directories."""
    mock_run = Mock()
    monkeypatch.setattr("xpython.deps.subprocess.run", mock_run)
    venv_python = tmp_path / "venv" / "bin" / "python"
    packages_dir = tmp_path / "packages"

    install_requirements(
        venv_python, ["requests", "attrs>=23"], packages_dir, ["/tmp/wheels"]
    )

    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] == [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--target",
        str(packages_dir),
        "--find-links",
        "/tmp/wheels",
        "requests",
        "attrs>=23",
    ]
    assert mock_run.call_args.kwargs["check"] is True
    assert mock_run.call_args.kwargs["env"]["XBUILD_ENV"] == "off"


def test_install_requirements_multiple_find_links(tmp_path, monkeypatch):
    """Multiple --find-links directories each get their own flag."""
    mock_run = Mock()
    monkeypatch.setattr("xpython.deps.subprocess.run", mock_run)
    venv_python = tmp_path / "venv" / "bin" / "python"
    packages_dir = tmp_path / "packages"

    install_requirements(venv_python, ["requests"], packages_dir, ["/tmp/a", "/tmp/b"])

    called_args = mock_run.call_args.args[0]
    assert called_args.count("--find-links") == 2
    assert "/tmp/a" in called_args
    assert "/tmp/b" in called_args


def test_install_requirements_disables_cross_venv_shim(tmp_path, monkeypatch):
    """install_requirements() runs pip with XBUILD_ENV=off so the cross-venv
    sys.platform shim doesn't interfere with pip's own ctypes usage."""
    mock_run = Mock()
    monkeypatch.setattr("xpython.deps.subprocess.run", mock_run)
    monkeypatch.setenv("SOME_OTHER_VAR", "keep-me")
    venv_python = tmp_path / "venv" / "bin" / "python"
    packages_dir = tmp_path / "packages"

    install_requirements(venv_python, ["requests"], packages_dir, [])

    called_env = mock_run.call_args.kwargs["env"]
    assert called_env["XBUILD_ENV"] == "off"
    assert called_env["SOME_OTHER_VAR"] == "keep-me"


def test_install_requirements_noop_when_empty(tmp_path, monkeypatch):
    """No pip call is made if there are no requirements to install."""
    mock_run = Mock()
    monkeypatch.setattr("xpython.deps.subprocess.run", mock_run)
    venv_python = tmp_path / "venv" / "bin" / "python"
    packages_dir = tmp_path / "packages"

    install_requirements(venv_python, [], packages_dir, [])

    mock_run.assert_not_called()
