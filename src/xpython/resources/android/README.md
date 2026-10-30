# Android testbed

This directory contains a copy of the Android testbed that CPython uses to run its own test suite on Android. `xpython` uses it to run code on an Android emulator or device, regardless of the Python version being targeted.

Except where noted below, these files are distributed under the terms of the Python Software Foundation License; see `LICENSE.python` in the root of the repository.

## Sources

The following files were copied from the `Platforms/Android` directory of the CPython `main` branch, at commit [`2188f9b60abb7965548b1f0eac368d858edfff80`](https://github.com/python/cpython/tree/2188f9b60abb7965548b1f0eac368d858edfff80/Platforms/Android):

- `android.py` (copied from `__main__.py`, renamed in the same way as CPython's official Android release packages);
- `android-env.sh`;
- `testbed/` (excluding the `.idea` Android Studio configuration).

The `legacy` directory contains files that are added to the testbed's `site-packages` when the target Python is older than 3.13, as those versions don't redirect `sys.stdout` and `sys.stderr` to the Android system log:

- `_android_support.py` was copied from `Lib/_android_support.py` on the CPython `3.13` branch, at commit [`ebc047f7179923a644416ebfe233109e1b9bbbc6`](https://github.com/python/cpython/blob/ebc047f7179923a644416ebfe233109e1b9bbbc6/Lib/_android_support.py);
- `_xpython_logcat.py` and `_xpython_logcat.pth` are part of `xbuild` (and are covered by `xbuild`'s own license), and install the redirection at interpreter startup.
