from __future__ import annotations

import dataclasses
import json
import pprint
import re
import sys
import venv
from importlib import import_module
from importlib import util as importlib_util
from pathlib import Path, PurePosixPath

from xvenv.fetch import fetch_python, resolve_arch, resolve_cache_path


@dataclasses.dataclass(frozen=True)
class CrossVenv:
    """The result of creating (or reusing) a cross-platform venv.

    :param platform: The platform for the cross venv.
    :param arch: The architecture of the cross venv.
    :param archive_path: The root of the target-platform Python
        archive that was used to build the venv (the same directory
        `xvenv.fetch.fetch_python()` extracted the download into). Contains
        platform-specific resources bundled inside the archive, such as the
        iOS/Android testbed projects.
    :param venv_path: The path to the cross-platform environment.
    """

    platform: str
    arch: str
    archive_path: Path
    venv_path: Path

    @property
    def description(self) -> str:
        return f"{self.platform} {self.arch}"


def create_cross_venv(
    venv_path: Path,
    platform: str,
    arch: str | None,
    build_details_path: Path | None,
    sysconfigdata_path: Path | None,
    cache_path: Path | None,
    with_pip: bool = True,
) -> Path:
    """Create (if `venv_path` doesn't already exist) and convert a virtual
    environment into a cross-platform venv for `platform`/`arch`, downloading
    (and caching) the target Python build as needed.

    :param venv_path: The path to the root of the venv. Created with
        `venv.create()` if it doesn't already exist; converted in place either
        way.
    :param platform: One of `"ios"`, `"android"`, `"emscripten"`.
    :param arch: The target architecture, or `None` to use a host-arch-based
        default (see `xvenv.fetch.resolve_arch()`).
    :path build_details_path: An explicit path to a build details JSON file.
        Ignored if `platform` is specified.
    :path sysconfigdata_path: An explicit path to a sysconfigdata python file.
        Ignored if `platform` is specified.
    :param cache_path: The directory to use for caching downloaded Python builds,
        or `None` to use the default resolution order (see
        `xvenv.fetch.resolve_cache_path()`).
    :param with_pip: Whether to install pip when creating the venv. Only
        relevant if `venv_path` doesn't already exist.
    :returns: A `CrossVenv` describing the resulting venv and the archive
        directory the target Python build was extracted into.
    :raises ValueError: on an unknown/unsupported arch, or any other error
        `resolve_arch()`, `fetch_python()`, or `convert_venv()` raise.
    :raises NotImplementedError: if `platform`/`arch` isn't supported for
        download yet (e.g. emscripten).
    """
    if not venv_path.exists():
        venv.create(venv_path, with_pip=with_pip)

    if platform is not None:
        resolved_cache_path = resolve_cache_path(cache_path)
        resolved_arch = resolve_arch(platform, arch)

        config_path, is_build_details = fetch_python(
            platform, resolved_arch, resolved_cache_path
        )

        resolved_build_details_path = config_path if is_build_details else None
        resolved_sysconfigdata_path = None if is_build_details else config_path

    else:
        resolved_build_details_path = (
            Path(build_details_path).resolve() if build_details_path else None
        )
        resolved_sysconfigdata_path = (
            Path(sysconfigdata_path).resolve() if sysconfigdata_path else None
        )

    return convert_venv(
        venv_path,
        build_details_path=resolved_build_details_path,
        sysconfigdata_path=resolved_sysconfigdata_path,
    )


def localized_vars(orig_vars, slice_path):
    """Update (where possible) any references to build-time variables with the best
    guess of the installed location."""
    # The host's sysconfigdata will include references to build-time variables.
    # Update these to refer to the current known install location.
    orig_prefix = orig_vars["prefix"]

    # The host's sysconfigdata may also include absolute paths to the
    # build machine's copy of the build toolchain (e.g. the Android NDK).
    # Identify that toolchain directory from CC, so it can be stripped from
    # every other variable that references it, leaving just the bare tool
    # name (to be resolved via PATH on whatever machine actually uses this
    # environment). If CC has no directory component (e.g. iOS's bare
    # "arm64-apple-ios-clang") or is missing, there's nothing to strip.
    # This is processed as a Posix path, as the build machine will always
    # be Posix.
    tool_dir = None
    cc = orig_vars.get("CC")
    if isinstance(cc, str):
        candidate = str(PurePosixPath(cc).parent)
        if candidate != ".":
            tool_dir = candidate

    localized_vars = {}
    for key, value in orig_vars.items():
        final = value
        if isinstance(value, str):
            # Replace any reference to the build machine's toolchain directory.
            # This must run *before* the install-prefix substitution, because
            # the toolchain *could* (and is, on official Android x86_64 builds)
            # be installed in the build prefix.
            if tool_dir is not None:
                final = final.replace(f"{tool_dir}/", "")
            # Replace any reference to the build prefix
            final = final.replace(orig_prefix, str(slice_path))
            # Replace any reference to the build-time Framework location
            final = final.replace("-F .", f"-F {slice_path}")
        localized_vars[key] = final

    # Remove LDLIBRARY from the sysconfig vars. At runtime, ctypes on Android
    # uses `sysconfig.get_config_var("LDLIBRARY")` to find libPython; this
    # fails in a cross-environment. Removing the LDLIBRARY key causes ctypes
    # to fall back to `ctypes.DLL(None)`, which is the default behavior on
    # desktop platforms anyway.
    localized_vars.pop("LDLIBRARY")

    return localized_vars


def localize_sysconfigdata(sysconfigdata_path, venv_site_packages):
    """Localize a sysconfigdata python module.

    :param support_path: The platform config that contains the sysconfigdata module to
        localize.
    :param venv_site_packages: The site packages folder where the localized
        sysconfigdata module should be output.
    """
    # Import the sysconfigdata module
    spec = importlib_util.spec_from_file_location(
        sysconfigdata_path.stem, sysconfigdata_path
    )
    if spec is None:
        msg = f"Unable to load spec for {sysconfigdata_path}"
        raise ValueError(msg)
    if spec.loader is None:
        msg = f"Spec for {sysconfigdata_path} does not define a loader"
        raise ValueError(msg)
    sysconfigdata = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(sysconfigdata)

    # Write the updated sysconfigdata module into the cross-platform site.
    slice_path = sysconfigdata_path.parent.parent.parent
    with (venv_site_packages / sysconfigdata_path.name).open("w") as f:
        f.write(f"# Generated from {sysconfigdata_path}\n")
        f.write("build_time_vars = ")
        pprint.pprint(
            localized_vars(sysconfigdata.build_time_vars, slice_path),
            stream=f,
            compact=True,
        )

    return sysconfigdata.build_time_vars


def localize_sysconfig_vars(sysconfig_vars_path, venv_site_packages):
    """Localize a sysconfig_vars.json file.

    :param support_path: The platform config that contains the sysconfigdata module to
        localize.
    :param venv_site_packages: The site-packages folder where the localized
        sysconfig_vars.json file should be output.
    :return: The localized sysconfig
    """
    with sysconfig_vars_path.open("rb") as f:
        build_time_vars = json.load(f)

    prefix = sysconfig_vars_path.parent.parent.parent
    sysconfig_vars = localized_vars(build_time_vars, prefix)

    with (venv_site_packages / sysconfig_vars_path.name).open("w") as f:
        json.dump(sysconfig_vars, f, indent=2)

    return sysconfig_vars


def convert_venv(
    venv_path: Path,
    build_details_path: Path | None,
    sysconfigdata_path: Path | None,
) -> CrossVenv:
    """Convert a virtual environment into a cross-platform environment.

    :param venv_path: The path to the root of the venv.
    :param build_details_path: The path to build-details.json file for the
        target platform.
    :param sysconfigdata_path: The path to the sysconfigdata python file for the
        target platform.
    :returns: A CrossVEnv value describing the environment that was created.
    """
    if not venv_path.exists():
        raise ValueError(f"Virtual environment {venv_path} does not exist.")

    if sys.platform == "win32":
        bin_path = "Scripts/python.exe"
        lib_glob = "Lib/site-packages"
    else:
        bin_path = "bin/python3"
        lib_glob = "lib/*/site-packages"
    if not (venv_path / bin_path).exists():
        raise ValueError(f"{venv_path} does not appear to be a virtual environment.")

    # Update path references in the sysconfigdata to reflect local conditions.
    platlibs = list(venv_path.glob(lib_glob))
    if len(platlibs) == 0:
        raise ValueError(f"Couldn't find site packages in {venv_path}")
    elif len(platlibs) > 1:
        raise ValueError(f"Found more than one site packages in {venv_path}")

    venv_site_packages_path = platlibs[0]
    if build_details_path:
        if not build_details_path.is_file():
            raise ValueError(f"Could not find {build_details_path}")

        # If build_details.json exists, then so does sysconfig_vars.
        with open(build_details_path) as fp:
            build_details = json.load(fp)

        # build_details platform is the full platform-min_version-multiarch
        # format. We only need the platform part.
        platform = build_details["platform"].split("-")[0]
        version = build_details["language"]["version"]
        abiflags = "".join(build_details["abi"]["flags"])
        multiarch = build_details["implementation"]["_multiarch"]

        localize_sysconfigdata(
            (
                build_details_path.parent
                / f"_sysconfigdata_{abiflags}_{platform}_{multiarch}.py"
            ),
            venv_site_packages_path,
        )
        localize_sysconfig_vars(
            (
                build_details_path.parent
                / f"_sysconfig_vars_{abiflags}_{platform}_{multiarch}.json"
            ),
            venv_site_packages_path,
        )
    elif sysconfigdata_path:
        if not sysconfigdata_path.is_file():
            raise ValueError(f"Could not find {sysconfigdata_path}")

        # If we've been given a sysconfigdata file, re
        _, _, abiflags, platform, multiarch = sysconfigdata_path.stem.split("_", 4)

        # Localize the sysconfig data.
        sysconfigdata = localize_sysconfigdata(
            sysconfigdata_path,
            venv_site_packages_path,
        )
        version = sysconfigdata["VERSION"]

        # We'll need to reconstruct build_details-like data once we have
        # a platform module, as the keys in sysconfig data vary by platform.
        build_details = None
    else:
        raise ValueError(
            "Must provide path to either build_details.json or sysconfigdata"
        )

    # Check the venv version matches the configuration file that has been provided
    venv_config = (venv_path / "pyvenv.cfg").read_text()

    match = re.search("version = (.*)", venv_config)
    if match:
        venv_version = match.groups()[0]
        if not venv_version.startswith(f"{version}."):
            raise ValueError(
                f"target venv is Python {venv_version}; "
                f"build details file is for Python {version}"
            )
    else:
        raise ValueError("Could not determine Python version from target venv.")

    # Generate the context for the templated cross-target file
    arch, sdk = multiarch.split("-", 1)
    context = {
        "platform": platform,
        "os": platform,  # some platforms use different capitalization here
        "multiarch": multiarch,
        "abiflags": abiflags,
        "arch": arch,
        "sdk": sdk,
    }

    try:
        platform_module = import_module(f"xvenv.platforms.{platform}")
        if build_details is None:
            build_details = platform_module.build_details_from_sysconfigdata(
                sysconfigdata
            )
            archive_path = platform_module.archive_path(sysconfigdata_path)
        else:
            archive_path = platform_module.archive_path(build_details_path)

        platform_module.extend_context(context, build_details)
    except ImportError:
        raise ValueError(
            f"Don't know how to build a cross-venv for {platform}"
        ) from None

    cross_multiarch = f"_cross_{platform}_{multiarch.replace('-', '_')}"

    # Render the template for the cross-target file.
    template = (Path(__file__).parent / "_cross_target.py.tmpl").read_text()
    rendered = template.format(**context)
    (venv_site_packages_path / f"{cross_multiarch}.py").write_text(rendered)

    # Write the .pth file that will enable the cross-target modifications
    (venv_site_packages_path / "_cross_venv.pth").write_text(
        f"import {cross_multiarch}\n"
    )

    return CrossVenv(
        platform=context["os"],
        arch=multiarch,
        archive_path=archive_path,
        venv_path=venv_path,
    )
