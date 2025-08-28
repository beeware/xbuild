import json
import pprint
from importlib import import_module
from importlib import util as importlib_util
from pathlib import Path


def localized_vars(orig_vars, slice_path):
    """Update (where possible) any references to build-time variables with the best
    guess of the installed location."""
    # The host's sysconfigdata will include references to build-time variables.
    # Update these to refer to the current known install location.
    orig_prefix = orig_vars["prefix"]
    localized_vars = {}
    for key, value in orig_vars.items():
        final = value
        if isinstance(value, str):
            # Replace any reference to the build installation prefix
            final = final.replace(orig_prefix, str(slice_path))
            # Replace any reference to the build-time Framework location
            final = final.replace("-F .", f"-F {slice_path}")
        localized_vars[key] = final

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


def convert_venv(venv_path: Path, sysconfig_vars_path: Path):
    """Convert a virtual environment into a cross-platform environment.

    :param venv_path: The path to the root of the venv.
    :param sysconfig_vars_path: The path to the sysconfig_vars JSON file for the target
        platform.
    """
    if not venv_path.exists():
        raise ValueError(f"Virtual environment {venv_path} does not exist.")
    if not (venv_path / "bin/python3").exists():
        raise ValueError(f"{venv_path} does not appear to be a virtual environment.")

    # Update path references in the sysconfigdata to reflect local conditions.
    platlibs = list(venv_path.glob("lib/*/site-packages"))
    if len(platlibs) == 0:
        raise ValueError(f"Couldn't find site packages in {venv_path}")
    elif len(platlibs) > 1:
        raise ValueError(f"Found more than one site packages in {venv_path}")

    venv_site_packages_path = platlibs[0]

    if not sysconfig_vars_path.is_file():
        raise ValueError(f"Could not find sysconfig file {sysconfig_vars_path}")

    if sysconfig_vars_path.parts[-2] != venv_site_packages_path.parts[-2]:
        raise ValueError(
            f"venv is {venv_site_packages_path.parts[-2]}; "
            f"sysconfig file is for {sysconfig_vars_path.parts[-2]}"
        )

    # Extract some basic properties from the name of the sysconfig_vars filename.
    _, _, _, abiflags, platform, multiarch = sysconfig_vars_path.stem.split("_")
    arch, sdk = multiarch.split("-", 1)

    # Localize the sysconfig data.
    sysconfig = localize_sysconfig_vars(sysconfig_vars_path, venv_site_packages_path)
    sysconfigdata_path = (
        sysconfig_vars_path.parent
        / f"_sysconfigdata_{abiflags}_{platform}_{multiarch}.py"
    )
    localize_sysconfigdata(sysconfigdata_path, venv_site_packages_path)

    # Generate the context for the templated cross-target file
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
        platform_module.extend_context(context, sysconfig)
    except ImportError:
        raise ValueError(
            f"Don't know how to build a cross-venv file for {platform}"
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

    return f"{context['os']} {multiarch}"
