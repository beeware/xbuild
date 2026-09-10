# Changelog

## Unreleased

* `xvenv` will now create the target virtual environment if it doesn't already exist, equivalent to running `python -m venv <location>` before conversion. Previously, `xvenv` required the target directory to already exist as a valid virtual environment.
* `xvenv` and `xbuild` can now be configured using a `build-details.json` file, as an alternative to a `sysconfig_vars` JSON file or `sysconfigdata` Python file.

## 0.2.0 (10 Sep 2025)

* Added `xbuild`, a PEP 517 build frontend that triggers cross-platform builds using a cross-platform virtual environment created by `xvenv`. Build requirements are installed for the build platform by default, unless listed in a new `target-requires` key in `build-system`, in which case they're installed for the target platform.

## 0.0.1 (5 Sep 2025)

Initial release.

* Includes `xvenv`, a tool for creating cross platform environments. This has undergone initial testing to verify it works for iOS, Android and Emscripten environments. The created environment is sufficient to trick `pip` into installing binaries for the target platform into the environment; and for tools like `wheel` to trigger builds with compiler invocations derived from `sysconfgdata`. This won't generally result in a *successful* build, as there will usually be other environmental requirements; but the a cross-platform build will be attempted.
