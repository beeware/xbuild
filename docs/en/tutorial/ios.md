# Tutorial: Building for iOS

This tutorial walks through the two most common `xbuild` tasks - creating a cross-platform virtual environment, and building a wheel - targeting iOS.

/// note | Before you start

To use `xbuild`, you'll need to be on a macOS machine with Xcode installed, and the iOS SDK added. See [Platform setup: iOS](../how-to/platform-setup/ios.md) for full details.

///

## Set up

Create a virtual environment for your build platform (macOS), and install `xbuild`:

```console
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ python -m pip install xbuild
```

## Create a cross-platform virtual environment

Use `xvenv` to create a cross-platform virtual environment targeting the iOS simulator:

```console
(venv) $ xvenv --platform ios --arch arm64-iphonesimulator x-venv
```

The first time you run this, `xbuild` downloads and caches a copy of Python built for the iOS simulator. Deactivate your build-platform virtual environment, and activate the new cross-platform one, to confirm it's pretending to be iOS:

```console
(venv) $ deactivate
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
ios
(x-venv) $ deactivate
```

## Build a wheel

If you have a project that contains a PEP 517 build configuration and has binary modules, you can build a binary wheel for the iOS simulator using:

```console
$ source venv/bin/activate
(venv) $ xbuild path/to/myproject --platform ios --arch arm64-iphonesimulator
```

This produces a wheel in `path/to/myproject/dist/`. You can confirm it's a real compiled binary wheel, not a pure-Python one, by checking its filename - it should look something like `myproject-0.1.0-cp313-cp313-ios_13_0_arm64_iphonesimulator.whl`, not `myproject-0.1.0-py3-none-any.whl`.

## Next steps

- [How to create a cross-platform virtual environment](../how-to/create-cross-venv.md) covers more advanced `xvenv` usage, like bringing your own Python build.
- [How to run a build](../how-to/run-a-build.md) covers more advanced `xbuild` usage, like target-platform build dependencies.
- [How `xbuild` works](../topics/how-it-works.md) explains the mechanism behind the cross-platform environment.
