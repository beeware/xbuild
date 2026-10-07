# `xpython`

`xpython` runs a Python module inside an iOS Simulator or Android emulator/device, using the same "testbed" project that Python uses to run its own test suite. This testbed is included as part of the official Python releases.

## Usage

```console
(venv) $ xpython --platform ios --src tests -d pytest -- -m pytest tests
(venv) $ xpython --platform android --group test -- -m pytest tests
```

`xpython` will:

1. Create a cross-platform virtual environment for the target `--platform`/`--arch`, downloading and caching the target Python build the same way `xvenv --platform ...` does.
2. Resolve dependencies (`-d`/`--dependency` specs and/or `--group` names from `[dependency-groups]` in `./pyproject.toml`) and install them using that environment's own `pip`.
3. Copy each `--src` path into the testbed's working directory.
4. Forward everything after `--` to the platform's testbed (see the `-- [args ...]` option below).
5. Run the project on a simulator/emulator
6. Exit with the exit code produced by the test code (or by the testbed driver itself, if it failed to build/launch before the test code could run).

If you use `--work-dir` to name a directory that was set up by a previous `xpython` invocation, steps 1-3 are skipped, and the existing testbed project is reused (see [`--work-dir`](#-work-dir-dir) below).

If you run `xpython` from inside an active cross-platform environment, you can omit `--platform`/`--build-details`/`--sysconfig`; `xpython` will target the platform of the current environment (see [Specifying the target platform](./index.md#target-platform)).

/// note | `xpython` in CI environments

`xpython` is able to run Android projects on macOS; but the macOS GitHub Actions environment isn't able to start an Android emulator. `xpython` will raise an error if it detects it is in a GitHub Actions environment and you try to run an Android project.

When `xpython` runs an Android project on Linux, and it is running in a GitHub Actions CI environment, and it will automatically enable [hardware accelerated virtualization](https://gitHub.blog/changelog/2024-04-02-gitHub-actions-hardware-accelerated-android-virtualization-now-available/).

///

See the [Common options](./index.md#common-options) page for options shared with `xbuild`/`xvenv`.

## Options

### `-d SPEC` / `--dependency SPEC`

A PEP 508 dependency specifier to install into the testbed (e.g. `requests`, `attrs>=23`, `mypkg[extra]`). Can be repeated.

### `--group NAME`

The name of a [PEP 735](https://peps.python.org/pep-0735/) dependency group, resolved against `[dependency-groups]` in `./pyproject.toml`. Can be repeated.

### `-f DIR` / `--find-links DIR`

A directory of local wheels to search during dependency resolution. Forwarded to pip's `--find-links`. PyPI is still available for anything not found locally. Can be repeated.

### `--src PATH`

A path to copy into the testbed's working directory (e.g. a test suite). Can be repeated.

### `--simulator NAME`

The name of the iOS simulator to use (e.g. `'iPhone 16e'`). Only valid with `--platform ios`.

### `--managed NAME`

The name of a Gradle-managed Android device to use. Defaults to `maxVersion` if neither `--managed` nor `--connected` is given. Only valid with `--platform android`.

### `--connected SERIAL`

The serial number of an already-connected Android device to use. Only valid with `--platform android`. Mutually exclusive with `--managed`.

### `--work-dir DIR`

Use this directory to store the cross-environment, installed dependencies, and testbed project, instead of a temporary directory. Unlike a temporary directory, this directory is **not** deleted when `xpython` exits.

If `DIR` doesn't exist, `xpython` creates it and sets up the testbed project in it. Once setup has completed successfully, `xpython` records the configuration of the project in `DIR/xpython.toml`.

If `DIR` already exists and was set up by a previous `xpython` invocation, the existing testbed project is reused. The cross-environment isn't recreated, the testbed isn't cloned again, and no sources or dependencies are installed. Only the run options (the arguments after `--`, `--simulator`, `--managed`, `--connected` and `--verbose`) are used. Setup options (`--platform`, `--arch`, `--cache`, `--archive`, `--build-details`, `--sysconfig`, `--dependency`, `--group`, `--find-links` and `--src`) can be omitted. If you do provide them and they differ from the options used to set up `DIR`, `xpython` prints a warning and ignores them.

```console
(venv) $ xpython --platform android --src tests --group test --work-dir build/android -- -m pytest tests
(venv) $ xpython --work-dir build/android -- -m pytest tests -k test_widget
```

Sources are copied, and dependencies installed, only when `DIR` is first set up. To pick up changes to your sources or dependencies, delete `DIR` and run `xpython` again.

If `DIR` exists but wasn't set up by `xpython` (or setup didn't complete successfully), `xpython` exits with an error.

### `-- [args ...]`

Everything after `--` is forwarded to the platform's testbed:

- **iOS**: the first forwarded argument must be `-m` (e.g. `-- -m pytest tests`). This mimics `python -m` invocation; the `-m` token itself is not passed through to the underlying test runner. If nothing follows `--`, no module is run and the testbed reports its own usage error.
- **Android**: forwarded arguments are passed through unchanged to the bundled `android.py test` driver's own `-- <args>` mechanism, which accepts `-m <module>`, `-c <code>`, or (if neither is given) defaults to running Python's own test suite via `-m test`.
