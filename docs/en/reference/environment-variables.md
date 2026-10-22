# Environment variables

## `XBUILD_CACHE`

The directory used to cache downloaded target-platform Python builds when using `--platform`, and (for Emscripten) automatically installed copies of the Emscripten SDK. Overridden by the `--cache` command-line option, which takes precedence. If neither is set, defaults to a platform-appropriate user cache directory (via [`platformdirs.user_cache_dir("xbuild")`](https://pypi.org/project/platformdirs/)).

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

## `XBUILD_PATH`

Additional directories to *prepend* to `PATH` when `xbuild` prepares the build environment for the target platform. Uses the same syntax as the platform's `PATH` variable.

This variable is honored on all platforms, but it is most useful when building for iOS. When building for iOS, `xbuild` replaces `PATH` with a minimal, clean value so that no build-machine tools leak into the build, but some builds still need specific build-machine tools (e.g. `cmake` or `ninja`). Directories in `XBUILD_PATH` are added ahead of that clean `PATH`:

```console
(venv) $ XBUILD_PATH=/opt/homebrew/opt/cmake/bin xbuild --platform ios --arch arm64-iphonesimulator
```

Directories in `XBUILD_PATH` take precedence over the tools `xbuild` provides for the target platform. Point `XBUILD_PATH` at directories that contain only the specific tools you need, rather than at a general directory like `/opt/homebrew/bin`, which could shadow the target-platform compiler or Python interpreter.

`XBUILD_PATH` only applies to builds performed by `xbuild`. It has no effect on a cross-platform environment that is activated and used directly.

## `XBUILD_COMPILER_WRAPPER_DIR`

Emscripten only. The directory in which `xbuild` creates its compiler wrappers (see [Platform setup: Emscripten](../how-to/platform-setup/emscripten.md#how-compilation-works)). If set, the directory is created if necessary and left in place after the build, which is useful for reproducing a compiler invocation by hand. If not set, a temporary directory is used and removed when `xbuild` exits.

Setting this variable does not, by itself, cause wrappers to be used; wrappers are only created and used when building for Emscripten.

## `SIDE_MODULE_CFLAGS`, `SIDE_MODULE_CXXFLAGS`, `SIDE_MODULE_LDFLAGS`

Emscripten only. Override the compiler and linker flags that the compiler wrappers add when compiling and linking extension modules. By default, these are derived from the configure-time flags of the target Python build.

## `MESON_CROSS_FILE`

Emscripten only. The [meson cross file](https://mesonbuild.com/Cross-compilation.html) passed to `meson setup` by the `meson` compiler wrapper. By default, `xbuild` writes a cross file describing the Emscripten target alongside the compiler wrappers.
