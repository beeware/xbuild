# Frequently Asked Questions

## What version of Python does `xbuild` support?

`xbuild` supports:

- Python {{ min_python_version }} or higher for iOS;
- Python {{ min_python_version }} or higher for Android;
- Python 3.14 or higher for Emscripten.

There are no official Android builds of Python 3.11 or 3.12, so `xbuild` uses the builds published by [Chaquopy](https://chaquo.com/chaquopy/) for those versions.

## How does `xbuild` work?

`xbuild`'s cross-compiling environments monkeypatch the Python interpreter at startup so that platform-detection functions return details about the target platform, not the build platform. See [How `xbuild` works](../topics/how-it-works.md) for the full explanation.
