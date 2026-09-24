# `xpython`

`xpython` runs a Python module inside an iOS Simulator or Android emulator/device, using the same "testbed" project that Python uses to run its own test suite. This testbed is included as part of the official Python releases.

## Usage

```console
(venv) $ xpython --platform ios --src tests -d pytest -- -m pytest tests
(venv) $ xpython --platform android --group test -- -m pytest tests
```

`xpython`:

1. Creates (or reuses) a cross-platform virtual environment for the target `--platform`/`--arch`, downloading and caching the target Python build the same way `xvenv --platform ...` does.
2. Resolves dependencies (`-d`/`--dependency` specs and/or `--group` names from `[dependency-groups]` in `./pyproject.toml`) and installs them using that environment's own `pip`.
3. Copies each `--src` path into the testbed's working directory.
4. Forwards everything after `--` to the platform's testbed (see the `-- [args ...]` option below).
5. Exits with the exit code produced by the module (or by the testbed driver itself, if it failed to build/launch before the module could run).

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

Use this directory to store the cross-environment, dependency install, and testbed staging, instead of a temporary directory. Unlike a temporary directory, this directory is **not** deleted when `xpython` exits — useful for inspecting a failed run.

### `-- [args ...]`

Everything after `--` is forwarded to the platform's testbed:

- **iOS**: the first forwarded argument must be `-m` (e.g. `-- -m pytest tests`). This mimics `python -m` invocation; the `-m` token itself is not passed through to the underlying test runner. If nothing follows `--`, no module is run and the testbed reports its own usage error.
- **Android**: forwarded arguments are passed through unchanged to the bundled `android.py test` driver's own `-- <args>` mechanism, which accepts `-m <module>`, `-c <code>`, or (if neither is given) defaults to running Python's own test suite via `-m test`.
