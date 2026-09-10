# Tutorial

To use xbuild, you need:

- an install of Python for the platform where you will be performing the build (e.g., macOS, Linux or Windows)
- a distribution of Python that has been compiled for your target platform (e.g., Android, Emscripten or iOS)

## Build a package

Create a virtual environment for your build platform (i.e., the platform where you will be compiling), and install `xbuild`:

```console
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ python -m pip install xbuild
```

You can then run `xbuild` from the root directory of the project you want to build. You *must* pass in the `--sysconfig` argument, providing the path to the `sysconfig_vars` JSON file for the target platform, or the equivalent `sysconfigdata` python configuration.

```console
(venv) $ python -m xbuild --sysconfig path/to/_sysconfig_vars__...json
```

This will create an isolated cross-platform virtual environment, and trigger a PEP 517 build in that environment. Any build `requires` will be installed *for the build platform*. For example, if you're running on macOS, building for an ARM64 iPhone simulator, and your project lists `ninja` as a requirement, the *macOS* version of ninja will be installed. This ensures that the binary will be executable during the build.

If, for some reason, you require the *iOS* version of a build requirement to be installed, you can specify `target-requires` in your `build-system` table. For example, to add the iOS version of "target-tool" to your isolated cross-build environment, you might use:

```toml
[build-system]
requires = ["setuptools"]
target-requires = ["target-tool"]
build-backend = "setuptools.build_meta"
```

In order for a cross-build to succeed, your environment must be configured appropriately for the platform you're targeting. This means setting `PATH` and other environment variables appropriately.

### Android

To build an Android wheel, you must:

- Have Android Studio or the Android Command-line Tools installed
- Have `ANDROID_HOME` configured in your environment
- Have a Java SDK installed
- Have `JAVA_HOME` defined in your environment

### iOS

You must have Xcode installed, with the iOS SDK added.

It is also strongly advised that you:

- Add the path to the iOS binary shims to your path. These are provided in the `Python.xcframework/ios-arm64/bin` and `Python.xcframework/ios-arm64_x86_64-simulator/bin` folder for the iOS support package that you have downloaded.

- Clear your path of any other dependencies. It is very easy for macOS ARM64 binaries from Homebrew and other sources to leak into iOS builds if they are present on the path; the safest approach is to set your path so it only contains:
    - The path for the Python binary (ideally, your virtual environment's `bin` directory)
    - `/usr/bin`
    - `/bin`
    - `/usr/sbin`
    - `/sbin`
    - `/Library/Apple/usr/bin`

### Emscripten

Coming soon...

## Creating a cross virtual environment

To explicitly create a cross-platform virtual environment, start by creating a virtual environment for your build platform (i.e., the platform where you will be compiling), then install and use the `xvenv` script to create cross-platform virtual environment.

```console
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ python -m pip install xbuild
(venv) $ python -m xvenv --sysconfig path/to/_sysconfig_vars__...json x-venv
```

If `x-venv` doesn't already exist, `xvenv` will create it first (equivalent to running `python -m venv x-venv`), then convert it into a cross environment. If `x-venv` already exists, it will be converted into a cross-platform environment of type specified by `--sysconfig`.

You can then deactivate the environment that was used to create the cross-platform environment, and activate the cross-platform virtual environment. For example, if `x-venv` was constructed using an iOS simulator sysconfig vars file (`_sysconfig_vars__ios_arm64-iphonesimulator.json`), you would see output like:

```console
(venv) $ deactivate
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
ios
(x-venv) $ python -c "import sys; print(sys.implementation._multiarch)"
arm64-iphonesimulator
```

This should now print the platform identifier for the target platform, not your build platform.

You can also configure xvenv with a `_sysconfigdata` Python file (e.g., `_sysconfigdata__ios_arm64-iphonesimulator.py`), instead of the `_sysconfig_var` JSON file. You'll have to use `_sysconfigdata` if you're on Python 3.13 (as the JSON format was only introduced in Python 3.14)

If you are in the cross-platform environment, and you need to temporarily convert it back to the build platform, you can do so with the `XBUILD_ENV` environment variable. For example, if `x-venv` is an iOS cross-platform environment:

```console
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
ios
(x-venv) $ XBUILD_ENV=off python -c "import sys; print(sys.platform)"
darwin
```

If you have an active cross-platform virtual environment, you can run `xbuild` without providing the `--sysconfig` variable. The configuration of your existing cross virtual environment will copied into the isolated environment for the build. Alternatively, you can also use the `--no-isolation` flag to disable the creation of a isolated cross-platform build environment. This will use your existing cross-platform environment as the build environment.
