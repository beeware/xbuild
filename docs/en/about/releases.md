# Release History

<!-- towncrier release notes start -->

## 0.3.1.dev6+g4cb83454f (2026-09-25)

### Features

* `xvenv` no longer produces output on success, matching the behavior of `venv` ([#87](https://github.com/beeware/xbuild/issues/87))
* Added a new `xpython` command, providing an entry point for running Python module inside an iOS Simulator or Android emulator/device testbed. ([#90](https://github.com/beeware/xbuild/issues/90))
* Added a `--archive` option to `xvenv`, `xbuild`, and `xpython`, allowing an already-extracted Python build to be used instead of downloading one via `--platform`. ([#92](https://github.com/beeware/xbuild/issues/92))

### Bugfixes

* `xvenv` no longer leaves build-machine-specific absolute paths (e.g. to the `CC`/`AR` provided by the Android NDK) in the localized `sysconfigdata` of a cross-platform environment. ([#10](https://github.com/beeware/xbuild/issues/10))

### Misc

* [#88](https://github.com/beeware/xbuild/issues/88), [#91](https://github.com/beeware/xbuild/issues/91)

## 0.3.0 (2026-09-22)

### Features

* `xvenv` and `xbuild` can now be configured using a `build-details.json` file, as an alternative to a `sysconfig_vars` JSON file or `sysconfigdata` Python file. ([#30](https://github.com/beeware/xbuild/issues/30))
* `xvenv` will now create the target virtual environment if it doesn't already exist, equivalent to running `python -m venv <location>` before conversion. Previously, `xvenv` required the target directory to already exist as a valid virtual environment. ([#79](https://github.com/beeware/xbuild/issues/79))
* `xbuild` and `xvenv` can now download and cache a matching Python build for a target platform automatically, using the `--platform {ios,android,emscripten}` option (with optional `--arch` and `--cache`), instead of requiring a pre-existing Python install and manually-providing the `--sysconfig`/`--build-details` option. ([#81](https://github.com/beeware/xbuild/issues/81))
* Support for cross-building iOS on Python 3.11 and 3.12 was added. ([#82](https://github.com/beeware/xbuild/issues/82))
* Support for Python 3.15 was added. ([#83](https://github.com/beeware/xbuild/issues/83))
* `xbuild` now exposes optional extras (like `virtualenv` and `uv`) that mirror the underlying `build` extras. ([#84](https://github.com/beeware/xbuild/issues/84))
* `xvenv` now supports `--without-pip`, matching `python -m venv`'s own flag, to skip installing pip when `xvenv` creates the target virtual environment. ([#86](https://github.com/beeware/xbuild/issues/86))

### Backward Incompatible Changes

* `xbuild` now requires `build` 1.6.0 or higher. ([#83](https://github.com/beeware/xbuild/issues/83))

### Documentation

* Added full documentation coverage for the `xbuild` and `xvenv` commands, including a command reference, platform-specific tutorials, how-to guides, and a topic guide explaining the cross-compilation mechanism. ([#85](https://github.com/beeware/xbuild/issues/85))

### Misc

* [#82](https://github.com/beeware/xbuild/issues/82), [#84](https://github.com/beeware/xbuild/issues/84)

## 0.2.0 (2025-09-10)

* Added `xbuild`, a PEP 517 build frontend that triggers cross-platform builds using a cross-platform virtual environment created by `xvenv`. Build requirements are installed for the build platform by default, unless listed in a new `target-requires` key in `build-system`, in which case they're installed for the target platform.

## 0.0.1 (2025-09-05)

Initial release.

* Includes `xvenv`, a tool for creating cross platform environments. This has undergone initial testing to verify it works for iOS, Android and Emscripten environments. The created environment is sufficient to trick `pip` into installing binaries for the target platform into the environment; and for tools like `wheel` to trigger builds with compiler invocations derived from `sysconfgdata`. This won't generally result in a *successful* build, as there will usually be other environmental requirements; but the a cross-platform build will be attempted.
