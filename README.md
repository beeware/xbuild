# xbuild

[![Python Versions](https://img.shields.io/pypi/pyversions/xbuild.svg)](https://pypi.python.org/pypi/xbuild)
[![PyPI Version](https://img.shields.io/pypi/v/xbuild.svg)](https://pypi.python.org/pypi/xbuild)
[![Maturity](https://img.shields.io/pypi/status/xbuild.svg)](https://pypi.python.org/pypi/xbuild)
[![BSD License](https://img.shields.io/pypi/l/xbuild.svg)](https://github.com/beeware/xbuild/blob/master/LICENSE)
[![Discord server](https://img.shields.io/discord/836455665257021440?label=Discord%20Chat&logo=discord&style=plastic)](https://beeware.org/bee/chat/)

`xbuild` is PEP517 build frontend that has additions and extensions to support cross-compiling wheels for platforms where compilation cannot be performed natively - most notably:

* Android
* Emscripten (WASM)
* iOS

## Usage

To use xbuild, you need:
* an install of Python for the platform where you will be performing the build (e.g., macOS, Linux or Windows)
* a distribution of Python that has been compiled for your target platform (e.g., Android, Emscripten or iOS)


### Build a package

Create a virtual environment for your build platform (i.e., the platform where you will be compiling), and install `xbuild`:

    $ python3 -m venv venv
    $ source venv/bin/activate
    (venv) $ python -m pip install xbuild

You can then run `xbuild` from the root directory of the project you want to build. You *must* pass in the `--sysconfig` argument, providing the path to the `sysconfig_vars` JSON file for the target platform, or the equivalent `sysconfigdata` python configuration.

    (venv) $ python -m xbuild --sysconfig path/to/_sysconfig_vars__...json

This will create an isolated cross-platform virtual environment, and trigger a PEP 517 build in that environment. Any build `requires` will be installed *for the build platform*. For example, if you're running on macOS, building for an ARM64 iPhone simulator, and your project lists `ninja` as a requirement, the *macOS* version of ninja will be installed. This ensures that the binary will be executable during the build.

If, for some reason, you require the *iOS* version of a build requirement to be installed, you can specify `target-requires` in your `build-system` table. For example, to add the iOS version of "target-tool" to your isolated cross-build environment, you might use:

    [build-system]
    requires = ["setuptools"]
    target-requires = ["target-tool"]
    build_backenmd = "setuptools.build_meta"

In order for a cross-build to succeed, your environment must be configured appropriately for the platform you're targeting.

#### Android

To build an Android wheel, you must:

* Have Android Studio or the Android Command-line Tools installed
* Have `ANDROID_HOME` configured in your environment
* Have a Java SDK installed
* Have `JAVA_HOME` defined in your environment

#### iOS

You must have Xcode installed, with the iOS SDK added.

It is also strongly advised that you:
* Add the path to the iOS binary shims to your path. These are provided in the `Python.xcframework/ios-arm64/bin` and `Python.xcframework/ios-arm64_x86_64-simulator/bin` folder for the iOS support package that you have downloaded.
* Clear your path of any other dependencies. It is very easy for macOS ARM64 binaries from Homebrew and other sources to leak into iOS builds if they are present on the path; the safest approach is to set your path so it only contains:
  - The path for the Python binary (ideally, your virtual environment's `bin` directory)
  - `/usr/bin`
  - `/bin`
  - `/usr/sbin`
  - `/sbin`
  - `/Library/Apple/usr/bin`

#### Emscripten

TODO

### Creating a cross virtual environment

To explicitly create a cross-platform virtual environment, start by creating a virtual environment for your build platform (i.e., the platform where you will be compiling), then use the `xvenv` script to convert that virtual environment in to a cross environment.

    $ python3 -m venv venv
    $ source venv/bin/activate
    (venv) $ python -m pip install xbuild
    (venv) $ python -m venv x-venv
    (venv) $ python -m xvenv --sysconfig path/to/_sysconfig_vars__...json x-venv

You can then deactivate the environment that was used to create the cross-platform environment, and activate the cross-platform virtual environment. For example, if `x-venv` was constructed using an iOS simulator sysconfig vars file (`_sysconfig_vars__ios_arm64-iphonesimulator.json`), you would see output like:

    (venv) $ deactivate
    $ source x-venv/bin/activate
    (x-venv) $ python -c "import sys; print(sys.platform)"
    ios
    (x-venv) $ python -c "import sys; print(sys.implementation._multiarch)"
    arm64-iphonesimulator

This should now print the platform identifier for the target platform, not your build platform.

You can also configure xvenv with a `_sysconfigdata` Python file (e.g., `_sysconfigdata__ios_arm64-iphonesimulator.py`), instead of the `_sysconfig_var` JSON file. You'll have to use `_sysconfigdata` if you're on Python 3.13 (as the JSON format was only introduced in Python 3.14)

If you are in the cross-platform environment, and you need to temporarily convert it back to the build platform, you can do so with the `XBUILD_ENV` environment variable. For example, if `x-venv` is an iOS cross-platform environment:

    $ source x-venv/bin/activate
    (x-venv) $ python -c "import sys; print(sys.platform)"
    ios
    (x-venv) $ XBUILD_ENV=off python -c "import sys; print(sys.platform)"
    darwin

If you have an active cross-platform virtual environment, you can run `xbuild` without providing the `--sysconfig` variable. The configuration of your existing cross virtual environment will copied into the isolated environment for the build. Alternatively, you can also use the `--no-isolation` flag to disable the creation of a isolated cross-platform build environment. This will use your existing cross-platform environment as the build environment.

## How this works

The cross build environment does not run the target platform binaries on the build platform - it uses binaries for the build platform, but monkey-patches the Python interpreter at startup so that any question asking details about the platform returns details about the target platform. For example, if you create an iOS cross-platform environment on a macOS machine, you'll be using the macOS `python.exe`; but if you ask for `sys.platform`, the answer will be `ios`, not `darwin`.

## Contributing

To set up a development environment:

    $ python3 -m venv venv
    $ source venv/bin/activate
    (venv) $ python -m pip install -U pip
    (venv) $ python -m pip install -e . --group dev

## Community

`xbuild` is part of the [BeeWare suite](http://beeware.org). You can talk to the community through:

- [@pybeeware on Twitter](https://twitter.com/pybeeware)
- [Discord](https://beeware.org/bee/chat/)

We foster a welcoming and respectful community as described in our [BeeWare Community Code of Conduct](http://beeware.org/community/behavior/).

## Contributing

If you experience problems with `xbuild`, [log them on GitHub](https://github.com/beeware/xbuild/issues). If you want to contribute code, please [fork the code](https://github.com/beeware/xbuild) and [submit a pull request](https://github.com/beeware/xbuild/pulls).
