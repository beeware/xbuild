# Frequently Asked Questions

## What version of Python does xbuild support?

Python {{ min_python_version }} or higher.

## How does xbuild work?

xbuild's cross-compiling environments monkeypatch the Python interpreter at startup so that platform-detection functions return details about the target platform, not the build platform. See [How xbuild works](../topics/how-it-works.md) for the full explanation.
