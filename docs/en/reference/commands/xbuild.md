# xbuild

`xbuild` is a [PEP 517](https://peps.python.org/0517) build frontend with additions and extensions to support cross-compiling wheels for platforms where compilation cannot be performed natively - most notably Android, Emscripten (WASM), and iOS.

`xbuild` only builds wheels; it does not build source distributions (sdists).

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

### `--no-isolation` / `-n` vs `--installer NAME`

`--no-isolation` disables building the project in an isolated virtual environment; build dependencies must already be installed in the environment `xbuild` is run from. This is mutually exclusive with `--installer`.

`--installer NAME` selects the Python package installer used to populate the isolated build environment. Defaults to `pip`. Valid choices are `pip` and `uv`; note that `xbuild` does not currently support `uv` for cross-compiling isolated environments (see [How to run a build](../../how-to/run-a-build.md) for details).

### `--build-details PATH` / `--sysconfig PATH` / `--platform {ios,android,emscripten}`

Exactly one of these three options is required, and they are mutually exclusive. They specify the target platform's Python configuration:

- `--platform {ios,android,emscripten}` - Download (or reuse a cached copy of) a Python build for the named target platform, matching the Python version currently running `xbuild`. See [How to run a build](../../how-to/run-a-build.md) and [Environment variables](../environment-variables.md) for how the download is cached.
- `--build-details PATH` - The path to a `build-details.json` file describing a pre-existing target-platform Python build (Python 3.14+ format).
- `--sysconfig PATH` - The path to a `_sysconfigdata__*.py` file describing a pre-existing target-platform Python build (legacy format, Python ≤3.13).

If you have an active cross-platform virtual environment (created with [`xvenv`](./xvenv.md)), you can omit all three of these options - the configuration of the active cross-venv is used instead.

### `--config-setting KEY[=VALUE]` / `-C KEY[=VALUE]` vs `--config-json JSON_STRING`

`--config-setting KEY[=VALUE]` (repeatable) passes a setting to the build backend. Settings beginning with a hyphen will erroneously be interpreted as options to `xbuild` if separated by a space character; use `--config-setting=--my-setting` or `-C--my-other-setting` instead.

`--config-json JSON_STRING` passes settings to the backend as a single JSON object, as an alternative to `--config-setting` for complex nested structures. Cannot be used together with `--config-setting`.

### `--arch ARCH`

The target architecture to use with `--platform`. Defaults to a useful value based on the host machine's architecture. Only valid in combination with `--platform`.

### `--cache PATH`

The directory to use for caching downloaded Python builds, for use with `--platform`. Defaults to the `XBUILD_CACHE` environment variable, or a platform-appropriate cache directory - see [Environment variables](../environment-variables.md). Only valid in combination with `--platform`.
