# `xvenv`

`xvenv` converts a native virtual environment into a cross-platform virtual environment - one that pretends to be running on a target platform (Android, Emscripten, or iOS) rather than the platform it's physically running on. See [How it works](../../topics/how-it-works.md) for the underlying mechanism.

## Usage

```console
(venv) $ xvenv --platform ios --arch arm64-iphonesimulator x-venv
```

If `x-venv` doesn't already exist, `xvenv` creates it first (equivalent to running `python -m venv x-venv`, with pip installed), then converts it into a cross environment. If `x-venv` already exists, it is converted into a cross-platform environment matching the platform/arch you specify.

See the [Common options](./index.md#common-options) page for options shared with `xbuild`.

## Options

### `--without-pip`

Skip installing `pip` when `xvenv` creates the target cross-platform virtual environment. Only relevant if the environment doesn't already exist; if you're converting a virtual environment that's already been created, the argument is ignored. Matches `python -m venv`'s own `--without-pip` flag.
