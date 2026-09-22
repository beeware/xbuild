# How `xbuild` works

`xbuild`'s cross-compiling environments don't run target-platform binaries on the build platform. Instead, they use build-platform binaries, but monkeypatch the Python interpreter at startup so that any question about the platform returns details about the *target* platform. For example, if you create an iOS cross-platform environment on a macOS machine, you're still using the macOS `python.exe` - but if you ask for `sys.platform`, the answer is `ios`, not `darwin`.

## The monkeypatch mechanism

When [`xvenv`](../reference/commands/xvenv.md) converts a virtual environment into a cross-platform environment, it writes a small Python module into the virtual environment's site-packages directory (named `_cross_<platform>_<multiarch>.py`, e.g. `_cross_ios_arm64_iphonesimulator.py`), along with a `_cross_venv.pth` file containing a single line: `import _cross_ios_arm64_iphonesimulator`. Because `.pth` files are processed by Python's `site` module at interpreter startup, this import happens automatically every time the virtual environment's Python is run - before any user code executes.

That generated module patches:

- **`sys`** - `sys.cross_compiling` is set to `True`; `sys.platform`, `sys.implementation._multiarch`, and `sys.abiflags` are set to the target platform's values; `sys.base_prefix`/`sys.base_exec_prefix` are set from the target's `sysconfig` data.
- **`os.uname()`** - returns target-platform-shaped values.
- **`platform`** - `platform.uname()` and platform-specific version functions (`platform.ios_ver()` for iOS, `platform.android_ver()` for Android) return target-platform-shaped values.
- **`subprocess`** - `subprocess._can_fork_exec` is forced to `True`, since the build-platform binary genuinely can fork/exec even though it's pretending to be a different platform.
- **`sysconfig`** - `sysconfig.get_platform()` and `sysconfig.get_sysconfigdata_name()` are overridden, and the `sysconfig` variable cache is forced to reload, so that subsequent `sysconfig.get_config_var(...)` calls return target-platform values.

## Three ways to point at a target Python

`xvenv` and `xbuild` both accept exactly one of `--platform`, `--build-details`, or `--sysconfig`. All three resolve to the same underlying "localized `sysconfigdata`" that actually drives the monkeypatch:

- `--build-details PATH` and `--sysconfig PATH` point directly at a pre-existing target-platform Python build's own configuration file (the Python 3.14+ `build-details.json` format, or the legacy `_sysconfigdata__*.py` format for Python ≤3.13, respectively).
- `--platform {ios,android,emscripten}` adds a download-and-cache step in front: it downloads (or reuses a cached copy of) a matching target-platform Python build, then locates that same kind of configuration file inside it, and proceeds identically to `--build-details`/`--sysconfig` from that point on.

In both cases, the configuration file is "localized" - path references to the *original* build machine's install prefix are rewritten to point at the new virtual environment's own location - before being used to generate the monkeypatch module described above.

## Isolated build environments

When [`xbuild`](../reference/commands/xbuild.md) creates its isolated build environment (the default, unless `--no-isolation` is given), it checks whether the *current* environment is already a cross-compiling environment (`sys.cross_compiling`):

- If not, the fresh isolated virtual environment is converted into a cross-platform environment directly, using whichever of `--platform`/`--build-details`/`--sysconfig` was provided.
- If it is (i.e. you're already inside an active cross-environment created by `xvenv`), the *active* environment's own cross-platform configuration and patch files are copied into the new isolated virtual environment instead, so the isolated build environment matches the one you're already in.

`--no-isolation` skips creating a separate isolated virtual environment altogether - the build runs directly in whatever environment `xbuild` itself was invoked from.

## `target-requires` vs `requires`

Standard PEP 517 `requires` is always installed *for the build platform*, even inside a target-patched cross-environment. This works because `xbuild` internally sets `XBUILD_ENV=off` (see [Environment variables](../reference/environment-variables.md#xbuild_env)) while installing `requires` dependencies, temporarily disabling the cross-platform patches so `pip` resolves and installs build-platform-native packages.

`target-requires` (see [Project configuration](../reference/project-configuration.md#target-requires)) is installed normally, without disabling the patches - so `pip` resolves and installs target-platform packages instead.
