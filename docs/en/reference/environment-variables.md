# Environment variables

## `XBUILD_CACHE`

The directory used to cache downloaded target-platform Python builds when using `--platform`. Overridden by the `--cache` command-line option, which takes precedence. If neither is set, defaults to a platform-appropriate user cache directory (via [`platformdirs.user_cache_dir("xbuild")`](https://pypi.org/project/platformdirs/)).

## `XBUILD_PATH`

Additional directories to *prepend* to `PATH` when `xbuild` prepares the build environment for the target platform. Use `os.pathsep` (`:` on macOS and Linux) to separate multiple directories.

This is most useful when building for iOS. `xbuild` replaces `PATH` with a minimal, clean value so that no build-machine tools leak into the build, but some builds still need specific build-machine tools (e.g., `cmake` or `ninja`). Directories in `XBUILD_PATH` are added ahead of that clean `PATH`:

```console
(venv) $ XBUILD_PATH=/opt/homebrew/opt/cmake/bin xbuild --platform ios --arch arm64-iphonesimulator
```

On other platforms, `XBUILD_PATH` is prepended to the inherited `PATH`. If `XBUILD_PATH` is unset or empty, `PATH` is not modified.

`XBUILD_PATH` only applies to builds performed by `xbuild`. It has no effect on a cross-platform environment that is activated and used directly.

## `XBUILD_ENV`

Controls whether an active cross-platform virtual environment's patches (to `sys`, `os`, `platform`, and `sysconfig` - see [How it works](../topics/how-it-works.md)) are applied. Set to `off` to temporarily make an active cross-platform environment behave like a normal build-platform environment:

```console
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
ios
(x-venv) $ XBUILD_ENV=off python -c "import sys; print(sys.platform)"
darwin
```

Clearing the variable, or setting it (case-insensitively) to `1` or `on`, leaves the cross-platform patches active.
