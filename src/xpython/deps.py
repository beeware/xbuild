from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

from dependency_groups import resolve as resolve_dependency_groups


def resolve_requirements(
    dependencies: list[str],
    groups: list[str],
    pyproject_path: Path,
) -> list[str]:
    """Merge `--dependency` specs with `--group` names expanded via PEP 735
    resolution against `pyproject_path`'s `[dependency-groups]` table.

    :param dependencies: PEP 508 requirement strings, passed through
        unchanged.
    :param groups: Names of groups to resolve from `[dependency-groups]` in
        `pyproject_path`.
    :param pyproject_path: The path to a `pyproject.toml` file. Only read
        if `groups` is non-empty.
    :returns: The expanded group requirements (in the order given),
        followed by `dependencies` (in the order given).
    :raises ValueError: if `groups` is non-empty and `pyproject_path`
        doesn't exist, or a named group isn't defined.
    """
    if not groups:
        return list(dependencies)

    if not pyproject_path.is_file():
        raise ValueError(
            f"Cannot resolve --group {groups!r}: {pyproject_path} does not exist."
        )

    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)

    dependency_groups_table = pyproject.get("dependency-groups", {})

    try:
        group_requirements = resolve_dependency_groups(dependency_groups_table, *groups)
    except LookupError as e:
        raise ValueError(str(e)) from e

    return [*group_requirements, *dependencies]


def install_requirements(
    venv_python: Path,
    requirements: list[str],
    packages_dir: Path,
    find_links: list[str],
) -> None:
    """Install `requirements` into `packages_dir`, using `venv_python`'s
    own `pip`.

    No-op if `requirements` is empty.

    :param venv_python: Path to the Python executable of the (cross-)venv
        whose pip should be used to resolve/install the requirements.
    :param requirements: PEP 508 requirement strings to install.
    :param packages_dir: The `--target` directory to install into.
    :param find_links: Directories to pass as `--find-links` (searched for
        local wheels before/alongside PyPI).
    :raises subprocess.CalledProcessError: if pip fails.
    """
    if not requirements:
        return

    command = [str(venv_python), "-m", "pip", "install", "--target", str(packages_dir)]
    for directory in find_links:
        command.extend(["--find-links", str(directory)])
    command.extend(requirements)

    env = {**os.environ, "XBUILD_ENV": "off"}
    subprocess.run(command, check=True, env=env)


__all__ = ["install_requirements", "resolve_requirements"]
