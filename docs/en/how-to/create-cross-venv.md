# How to create a cross-platform virtual environment

[`xvenv`](../reference/commands/xvenv.md) converts a virtual environment so that it pretends to be running on a target platform, rather than the platform it's physically running on. This is required when a platform requires building an application on one platform, for deployment on a second platform (e.g., building a mobile application on a desktop machine that will be run on a mobile phone.

Before you start, make sure your build-platform machine is set up for your chosen target platform - see [Platform setup](platform-setup/index.md).

## Creating the environment

Start by creating (or reusing) a virtual environment for your **build** platform, and install `xbuild`:

```console
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ python -m pip install xbuild
```

Then run `xvenv`, specifying the platform and architecture you want to target, and the path where the cross-environment should be created:

```console
(venv) $ xvenv --platform ios --arch arm64-iphonesimulator x-venv
```

If the `x-venv` directory doesn't already exist, `xvenv` creates it first (equivalent to running `python -m venv x-venv`), then converts it into a cross environment. If `x-venv` already exists, it is converted in place.

## Activating the cross-environment

Deactivate the build-platform virtual environment you used to create the cross-environment, then activate the cross-environment itself:

```console
(venv) $ deactivate
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
ios
(x-venv) $ python -c "import sys; print(sys.implementation._multiarch)"
arm64-iphonesimulator
```

The output confirms the platform identifier is now the *target* platform, not the build platform.

## Using an existing Python build

If you already have a target-platform Python build downloaded (rather than letting `xvenv` download and cache one for you via `--platform`), point `xvenv` at its configuration file directly:

```console
(venv) $ xvenv --sysconfig path/to/_sysconfigdata__ios_arm64-iphonesimulator.py x-venv
```

Use `--sysconfig` to point at a `_sysconfigdata__*.py` file if you're on Python 3.13 or earlier (the JSON `build-details.json` format was only introduced in Python 3.14). Use `--build-details` to point at a `build-details.json` file on Python 3.14+.

## Temporarily reverting to the build platform

If you're in a cross-platform environment and need to temporarily run something as the build platform (for example, a build-platform-only tool), use the `XBUILD_ENV` environment variable:

```console
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
ios
(x-venv) $ XBUILD_ENV=off python -c "import sys; print(sys.platform)"
darwin
```

See [Environment variables](../reference/environment-variables.md#xbuild_env) for the full reference.
