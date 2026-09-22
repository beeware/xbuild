# Tutorial: building for Android

This tutorial walks through the two most common xbuild tasks - creating a cross-platform virtual environment, and building a wheel - targeting Android.

/// note | Before you start

You'll need Android Studio (or the command-line tools), `ANDROID_HOME`, and a JDK with `JAVA_HOME` set. See [Platform setup: Android](../how-to/platform-setup/android.md) for full details.

///

## Set up

Create a virtual environment for your build platform, and install `xbuild`:

/// tab | macOS/Linux

```console
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ python -m pip install xbuild
```

///

/// tab | Windows

```doscon
C:\...> python3 -m venv venv
C:\...> venv\Scripts\activate
(venv) C:\...> python -m pip install xbuild
```

///

## Create a cross-platform venv

Use `xvenv` to create a cross-platform virtual environment targeting Android (using the `aarch64` architecture, typical for both physical devices and Apple Silicon-hosted emulators):

```console
(venv) $ xvenv --platform android --arch aarch64 x-venv
```

The first time you run this, xbuild downloads and caches a copy of Python built for Android. Deactivate your build-platform venv, and activate the new cross-platform one, to confirm it's pretending to be Android:

/// tab | macOS/Linux

```console
(venv) $ deactivate
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
android
(x-venv) $ deactivate
```

///

/// tab | Windows

```doscon
(venv) C:\...> deactivate
C:\...> x-venv\Scripts\activate
(x-venv) C:\...> python -c "import sys; print(sys.platform)"
android
(x-venv) C:\...> deactivate
```

///

## Build a wheel

Clone or copy the xbuild repository so you have access to the `tests/samples/test1` sample project (a minimal package containing a C extension), then build it for Android:

/// tab | macOS/Linux

```console
$ source venv/bin/activate
(venv) $ xbuild tests/samples/test1 --platform android --arch aarch64
```

///

/// tab | Windows

```doscon
C:\...> venv\Scripts\activate
(venv) C:\...> xbuild tests\samples\test1 --platform android --arch aarch64
```

///

This produces a wheel in `tests/samples/test1/dist/`. Confirm it's a real compiled binary wheel, not a pure-Python one, by checking its filename - it should look something like `test1-0.1.0-cp313-cp313-android_24_arm64_v8a.whl`, not `test1-0.1.0-py3-none-any.whl`.

## Next steps

- [How to create a cross-platform venv](../how-to/create-cross-venv.md) covers more advanced `xvenv` usage, like bringing your own Python build.
- [How to run a build](../how-to/run-a-build.md) covers more advanced `xbuild` usage, like target-platform build dependencies.
- [How xbuild works](../topics/how-it-works.md) explains the mechanism behind the cross-platform environment.
