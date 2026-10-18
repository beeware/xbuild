"""Redirect `sys.stdout` and `sys.stderr` to the Android system log.

Python 3.13+ does this itself during interpreter startup (see
`init_android_streams()` in `Python/pylifecycle.c`). Earlier versions don't,
so the testbed driver (which only reports the `python.stdout` and
`python.stderr` log tags) would never see the output of the program being run.
This module is loaded by `_xpython_logcat.pth` to perform the same redirection
using a copy of Python 3.13's `_android_support` module.
"""

import ctypes

import _android_support

_android_log_write_fn = ctypes.CDLL("liblog.so")["__android_log_write"]
_android_log_write_fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p]


def _android_log_write(prio, tag, message):
    _android_log_write_fn(prio, tag.encode("UTF-8"), message)


# These log priorities (ANDROID_LOG_INFO and ANDROID_LOG_WARN) match those used
# by Python 3.13+, and by Java's System.out and System.err.
_android_support.init_streams(_android_log_write, 4, 5)
