# Frequently Asked Questions

## What version of Python does `xbuild` support?

`xbuild` supports:

- Python {{ min_python_version }} or higher for iOS;
- Python 3.13 or higher for Android.
- Python 3.14 or higher for Emscripten.

## How does `xbuild` work?

`xbuild`'s cross-compiling environments monkeypatch the Python interpreter at startup so that platform-detection functions return details about the target platform, not the build platform. See [How `xbuild` works](../topics/how-it-works.md) for the full explanation.
