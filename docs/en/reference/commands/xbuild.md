# `xbuild`

`xbuild` is a [PEP 517](https://peps.python.org/0517) build frontend with additions and extensions to support cross-compiling wheels for platforms where compilation cannot be performed natively - most notably Android, Emscripten (WASM), and iOS.

`xbuild` only builds wheels; it does not build source distributions (`sdists`).

## Usage

Run `xbuild` from the root directory of the project you want to build, specifying the source of the target platform's Python configuration with exactly one of `--build-details`, `--sysconfig`, or `--platform`:

```console
(venv) $ xbuild --platform ios --arch arm64-iphonesimulator
```

You can also specify an explicit source directory:

```console
(venv) $ xbuild path/to/project --platform ios --arch arm64-iphonesimulator
```

If `srcdir` is omitted, it defaults to the current directory.

See the [Common options](./index.md#common-options) page for options shared with `xvenv`.

## Options

### `--outdir PATH` / `-o PATH`

The output directory for the built wheel. Defaults to `{srcdir}/dist`.

### `--skip-dependency-check` / `-x`

Do not check that build dependencies are installed. Only meaningful with `--no-isolation`, since an isolated build always installs its own dependencies.

### `--no-isolation` / `-n` { #xbuild-no-isolation }

`--no-isolation` disables building the project in an isolated virtual environment; build dependencies must already be installed in the environment `xbuild` is run from. This is mutually exclusive with `--installer`.

### `--installer NAME`

`--installer NAME` selects the Python package installer used to populate the isolated build environment. Defaults to `pip`. Valid choices are `pip` and `uv`; note that `xbuild` does not currently support `uv` for cross-compiling isolated environments (see [How to run a build](../../how-to/run-a-build.md) for details).

### `--config-setting KEY[=VALUE]` / `-C KEY[=VALUE]` { #xbuild-config-setting }

`--config-setting KEY[=VALUE]` (repeatable) passes a setting to the build backend. Settings beginning with a hyphen will erroneously be interpreted as options to `xbuild` if separated by a space character; use `--config-setting=--my-setting` or `-C--my-other-setting` instead.

### `--config-json JSON_STRING` { #xbuild-config-json }

`--config-json JSON_STRING` passes settings to the backend as a single JSON object, as an alternative to `--config-setting` for complex nested structures. Cannot be used together with [`--config-setting`][xbuild-config-setting].
