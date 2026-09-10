# Frequently Asked Questions

## What version of Python does xbuild support?

Python {{ min_python_version }} or higher.

## How does xbuild work?

The cross build environment does not run the target platform binaries on the build platform - it uses binaries for the build platform, but monkey-patches the Python interpreter at startup so that any question asking details about the platform returns details about the target platform. For example, if you create an iOS cross-platform environment on a macOS machine, you'll be using the macOS `python.exe`; but if you ask for `sys.platform`, the answer will be `ios`, not `darwin`.
