from __future__ import annotations

import json
import pprint
import re
import sys
import venv
from importlib import import_module
from pathlib import Path, PurePosixPath
from types import ModuleType

from xvenv.fetch import (
    fetch_python,
    parse_sysconfigdata,
    resolve_arch,
    resolve_cache_path,
    use_archive_path,
)


class CrossVenvConfig:
    platform: str
    arch: str
    archive_path: Path
    platform_module: ModuleType
    build_details_path: Path | None
    sysconfigdata_path: Path | None

    def __init__(
        self,
        *,
        platform: str | None,
        arch: str | None,
        archive_path: Path | None = None,
        build_details_path: Path | None,
        sysconfigdata_path: Path | None,
        cache_path: Path | None,
    ) -> CrossVenvConfig:
        """A configuration for a cross-platform virtual environment.

        Uses a combination of `platform`, `arch`, `archive_path`,
        `build_details_path`, `sysconfigdata_path` and `cache_path` to resolve a
        complete set of configuration details for a cross-platform virtual
        environment, downloading (and caching) a target Python build if
        `platform` is given and `archive_path` is not.

        This configuration can then be converted into a new cross-platform
        environment using `create()`; or an existing environment can be
        converted using `convert()`.

        :param platform: One of `"ios"`, `"android"`, `"emscripten"`, or `None`
            to use `build_details_path`/`sysconfigdata_path` directly.
        :param arch: The target architecture, or `None` to use a host-arch-based
            default (see `xvenv.fetch.resolve_arch()`). Ignored if `platform` is
            `None`.
        :param archive_path: The path to an already-extracted Python build to
            use instead of downloading one, or `None` to download (and cache) as
            usual. Ignored if `platform` is not specified.
        :param build_details_path: An explicit path to a build details JSON
            file. Ignored if `platform` is specified.
        :param sysconfigdata_path: An explicit path to a sysconfigdata python
            file. Ignored if `platform` is specified.
        :param cache_path: The directory to use for caching downloaded Python
            builds, or `None` to use the default resolution order (see
            `xvenv.fetch.resolve_cache_path()`). Ignored if `archive_path` is
            given, or if `platform` is `None`.
        :returns: The resolved `CrossVenvConfig`.
        :raises NotImplementedError: if `platform`/`arch` isn't supported for
            download yet (e.g. emscripten).
        """
        if platform is not None:
            arch = resolve_arch(platform, arch)

            if archive_path is not None:
                config_path, is_build_details = use_archive_path(
                    platform, arch, Path(archive_path).resolve()
                )
            else:
                cache_path = resolve_cache_path(cache_path)
                config_path, is_build_details = fetch_python(platform, arch, cache_path)

            self.build_details_path = config_path if is_build_details else None
            self.sysconfigdata_path = None if is_build_details else config_path
        else:
            self.build_details_path = (
                Path(build_details_path).resolve() if build_details_path else None
            )
            self.sysconfigdata_path = (
                Path(sysconfigdata_path).resolve() if sysconfigdata_path else None
            )

        if self.build_details_path:
            if not self.build_details_path.is_file():
                raise ValueError(f"Could not find {self.build_details_path}")
            with open(self.build_details_path) as fp:
                build_details = json.load(fp)
            self.platform = build_details["platform"].split("-")[0]
            self.arch = build_details["implementation"]["_multiarch"]
            source_path = self.build_details_path
        elif self.sysconfigdata_path:
            if not self.sysconfigdata_path.is_file():
                raise ValueError(f"Could not find {self.sysconfigdata_path}")
            _, _, _, self.platform, self.arch = self.sysconfigdata_path.stem.split(
                "_", 4
            )
            source_path = self.sysconfigdata_path
        else:
            raise ValueError(
                "Must provide path to either build_details.json or sysconfigdata"
            )

        try:
            self.platform_module = import_module(f"xvenv.platforms.{self.platform}")
        except ImportError:
            raise ValueError(
                f"Don't know how to build a cross-venv for {self.platform}"
            ) from None

        self.archive_path = self.platform_module.archive_path(source_path)

    @property
    def description(self) -> str:
        name = "iOS" if self.platform == "ios" else self.platform.capitalize()
        return f"{name} {self.arch}"

    def convert(self, venv_path: Path) -> None:
        """Convert a virtual environment into a cross-platform environment.

        :param venv_path: The path to the root of the venv.
        :param config: The resolved target-platform configuration (see
            `resolve_cross_venv_config()`).
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
            raise ValueError(
                f"{venv_path} does not appear to be a virtual environment."
            )

        # Update path references in the sysconfigdata to reflect local conditions.
        platlibs = list(venv_path.glob(lib_glob))
        if len(platlibs) == 0:
            raise ValueError(f"Couldn't find site packages in {venv_path}")
        elif len(platlibs) > 1:
            raise ValueError(f"Found more than one site packages in {venv_path}")

        venv_site_packages_path = platlibs[0]
        if self.build_details_path:
            # If build_details.json exists, then so does sysconfig_vars.
            with open(self.build_details_path) as fp:
                build_details = json.load(fp)

            version = build_details["language"]["version"]
            abiflags = "".join(build_details["abi"]["flags"])

            localize_sysconfigdata(
                (
                    self.build_details_path.parent
                    / f"_sysconfigdata_{abiflags}_{self.platform}_{self.arch}.py"
                ),
                venv_site_packages_path,
            )
            localize_sysconfig_vars(
                (
                    self.build_details_path.parent
                    / f"_sysconfig_vars_{abiflags}_{self.platform}_{self.arch}.json"
                ),
                venv_site_packages_path,
            )
        else:
            # We've been given a sysconfigdata file instead.
            _, _, abiflags, _, _ = self.sysconfigdata_path.stem.split("_", 4)

            # Localize the sysconfig data.
            sysconfigdata = localize_sysconfigdata(
                self.sysconfigdata_path,
                venv_site_packages_path,
            )
            version = sysconfigdata["VERSION"]

            # We'll need to reconstruct build_details-like data once we have
            # a platform module, as the keys in sysconfig data vary by platform.
            build_details = None

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
        arch, sdk = self.arch.split("-", 1)
        context = {
            "platform": self.platform,
            "os": self.platform,  # some platforms use different capitalization here
            "multiarch": self.arch,
            "abiflags": abiflags,
            "arch": arch,
            "sdk": sdk,
        }

        if build_details is None:
            build_details = self.platform_module.build_details_from_sysconfigdata(
                sysconfigdata
            )
        self.platform_module.extend_context(context, build_details)

        cross_multiarch = f"_cross_{self.platform}_{self.arch.replace('-', '_')}"

        # Render the template for the cross-target file.
        template = (Path(__file__).parent / "_cross_target.py.tmpl").read_text()
        rendered = template.format(**context)
        (venv_site_packages_path / f"{cross_multiarch}.py").write_text(rendered)

        # Write the .pth file that will enable the cross-target modifications
        (venv_site_packages_path / "_cross_venv.pth").write_text(
            f"import {cross_multiarch}\n"
        )

    def create(self, venv_path: Path, with_pip: bool = True):
        """Create (if `venv_path` doesn't already exist) and convert a virtual
        environment into a cross-platform venv for `platform`/`arch`,
        downloading (and caching) the target Python build as needed.

        :param venv_path: The path to the root of the venv. Created if it
            doesn't already exist; converted in place either way.
        :param with_pip: Whether to install pip when creating the venv. Only
            relevant if `venv_path` doesn't already exist.
        """
        if not venv_path.exists():
            venv.create(venv_path, with_pip=with_pip)

        self.convert(venv_path)

    def prepare_env(self) -> dict[str, str]:
        """Prepare the environment variables needed to build for this cross environment.

        :returns: A dict of environment variables to merge into `os.environ`
            for the duration of the build.
        :raises ValueError: if the platform module's own `prepare_env()`
            raises (e.g. missing `ANDROID_HOME`, missing NDK, non-macOS for
            iOS).
        :raises NotImplementedError: for platforms that don't support
            environment preparation yet (currently: emscripten).
        """
        return self.platform_module.prepare_env(self)

    def packages_path(self, work_path: Path) -> Path:
        """Return the location, relative to the provided path, where the
        platform requires user-installed packages are installed.
        """
        return self.platform_module.packages_path(work_path)

    def setup_testbed(self, work_path: Path, src_paths: list[Path]):
        """Clone the testbed, and install source files into it.

        :param work_path: The working directory to clone the testbed into.
        :param src_paths: Paths to copy into the cloned testbed's src directory.
        :raises RuntimeError: if the platform isn't compatible with the runtime
            conditions.
        """
        return self.platform_module.setup_testbed(
            archive_path=self.archive_path,
            work_path=work_path,
            src_paths=src_paths,
        )

    def run_testbed(
        self,
        work_path: Path,
        args: list[str],
        verbose: int,
        **kwargs,
    ) -> int:
        """Run the testbed project in the cross-platform environment.

        :param work_path: The working directory for the testbed.
        :param args: Arguments to pass to the testbed process. Accepts any
            argument list starting with `-c`/`-m`; defaults to `-m test`
            if `args` is empty.
        :param verbose: Verbosity level.
        :param kwargs: Any additional platform-specific arguments.
        :returns: The exit code of the testbed subprocess.
        """
        return self.platform_module.run_testbed(
            work_path=work_path,
            args=args,
            verbose=verbose,
            **kwargs,
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
    sysconfigdata = parse_sysconfigdata(sysconfigdata_path)

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
