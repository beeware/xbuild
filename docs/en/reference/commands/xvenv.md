# xvenv

`xvenv` converts a native virtual environment into a cross-platform virtual environment - one that pretends to be running on a target platform (Android, Emscripten, or iOS) rather than the platform it's physically running on. See [How it works](../../topics/how-it-works.md) for the underlying mechanism.

## Usage

```console
(venv) $ xvenv --platform ios --arch arm64-iphonesimulator x-venv
```

If `x-venv` doesn't already exist, `xvenv` creates it first (equivalent to running `python -m venv x-venv`, with pip installed), then converts it into a cross environment. If `x-venv` already exists, it is converted into a cross-platform environment matching the platform/arch you specify.

See the [Common options](./index.md#common-options) page for options shared with `xbuild`.

## Options

### `--build-details` / `--sysconfig` / `--platform`

Exactly one of these three options is required, and they are mutually exclusive. Same semantics as [xbuild's equivalent options](./xbuild.md#-build-details-path-sysconfig-path-platform-iosandroidemscripten) - unlike `xbuild`, `xvenv` has no "already have an active cross-venv" fallback, since creating that cross-venv is exactly what `xvenv` is for.

### `--arch`

Same as [xbuild's `--arch`](./xbuild.md#-arch-arch). Only valid in combination with `--platform`.

### `--cache`

Same as [xbuild's `--cache`](./xbuild.md#-cache-path). Only valid in combination with `--platform`.
