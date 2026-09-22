# Tutorial: building for iOS

This tutorial walks through the two most common xbuild tasks - creating a cross-platform virtual environment, and building a wheel - targeting iOS.

/// note | Before you start

You'll need Xcode installed, with the iOS SDK added. See [Platform setup: iOS](../how-to/platform-setup/ios.md) for full details.

///

## Set up

Create a virtual environment for your build platform (macOS), and install `xbuild`:

```console
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ python -m pip install xbuild
```

## Create a cross-platform venv

Use `xvenv` to create a cross-platform virtual environment targeting the iOS simulator:

```console
(venv) $ xvenv --platform ios --arch arm64-iphonesimulator x-venv
```

The first time you run this, xbuild downloads and caches a copy of Python built for the iOS simulator. Deactivate your build-platform venv, and activate the new cross-platform one, to confirm it's pretending to be iOS:

```console
(venv) $ deactivate
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
ios
(x-venv) $ deactivate
```

## Build a wheel

Clone or copy the xbuild repository so you have access to the `tests/samples/test1` sample project (a minimal package containing a C extension), then build it for the iOS simulator:

```console
$ source venv/bin/activate
(venv) $ xbuild tests/samples/test1 --platform ios --arch arm64-iphonesimulator
```

This produces a wheel in `tests/samples/test1/dist/`. Confirm it's a real compiled binary wheel, not a pure-Python one, by checking its filename - it should look something like `test1-0.1.0-cp313-cp313-ios_13_0_arm64_iphonesimulator.whl`, not `test1-0.1.0-py3-none-any.whl`.

## Next steps

- [How to create a cross-platform venv](../how-to/create-cross-venv.md) covers more advanced `xvenv` usage, like bringing your own Python build.
- [How to run a build](../how-to/run-a-build.md) covers more advanced `xbuild` usage, like target-platform build dependencies.
- [How xbuild works](../topics/how-it-works.md) explains the mechanism behind the cross-platform environment.
