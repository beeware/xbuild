# Set up your environment for Emscripten

To build for Emscripten (Pyodide), you must:

- Have `git` and `bash` available (used to install the Emscripten SDK); and
- Have [Node](https://nodejs.org) 18 or later on your `PATH` (used by `xpython`, and by `meson`-based builds to run build-time checks).

`xvenv` can be used on any desktop operating system. However, `xbuild` can only be used on macOS and Linux. It is not possible to use `xbuild` to build Emscripten wheels on Windows.

Emscripten is supported for Python 3.12, 3.13 and 3.14.

## The target Python

When you use `--platform emscripten`, `xvenv` and `xbuild` download the [Pyodide](https://pyodide.org) cross-build environment that matches your Python version (for example, Pyodide 314.0.7 for Python 3.14), and cache it in [`XBUILD_CACHE`](../../reference/environment-variables.md#xbuild_cache). The only supported `--arch` is `wasm32`.

You can also point `--build-details` or `--sysconfig` at an existing Emscripten build of Python. The build must record a Pyodide ABI version (`PYODIDE_ABI_VERSION`) in its configuration; builds from the Pyodide cross-build environment do.

## The Emscripten SDK

Pyodide requires that extension modules are compiled with the *same* version of Emscripten (with the same patches) that was used to build the interpreter.

If `emcc` is on your `PATH` at the version required by the target Python, `xbuild` uses it as-is. Otherwise, `xbuild` installs the required version of the [Emscripten SDK](https://emscripten.org/docs/getting_started/downloads.html) into `XBUILD_CACHE` (as `emsdk_<version>`), applies the patches that Pyodide requires to it, and activates it for the duration of the build. This is a large download, and only happens once per Emscripten version.

If `emcc` is on your `PATH` at a *different* version, `xbuild` says so, and installs and uses the required version instead.

## How compilation works

`xbuild` creates a directory of "compiler wrappers" (`cc`, `c++`, `ar`, `cmake`, `meson`, and so on), puts that directory at the front of `PATH`, and sets `CC`, `CXX`, `AR`, etc. to point at the wrappers. Each wrapper rewrites the arguments it is given to be suitable for Emscripten (dropping unsupported flags, removing duplicate libraries, adding the side-module export list) and then invokes the corresponding Emscripten tool (`emcc`, `em++`, `emar`, `emcmake`, ...). This is a port of the `pywasmcross` wrapper from [pyodide-build](https://github.com/pyodide/pyodide-build).

The compiler flags used for extension modules are derived from the configure-time flags of the target Python build. They can be overridden by setting `SIDE_MODULE_CFLAGS`, `SIDE_MODULE_CXXFLAGS` or `SIDE_MODULE_LDFLAGS` in your environment.

`meson`-based builds (e.g., `meson-python`) are given a [cross file](https://mesonbuild.com/Cross-compilation.html) describing the Emscripten target, which is written alongside the wrappers. Set `MESON_CROSS_FILE` to use your own cross file instead.

By default, the wrapper directory is created in a temporary location and removed when `xbuild` exits. To keep it (for example, to reproduce a compiler invocation by hand), set [`XBUILD_COMPILER_WRAPPER_DIR`](../../reference/environment-variables.md#xbuild_compiler_wrapper_dir) to the directory that should be used.

### Known limitations

- Rust extensions (`maturin`, `setuptools-rust`) are not supported: `cargo` is not wrapped, and the Rust toolchain for the `wasm32-unknown-emscripten` target is not configured.
- Fortran code is not supported.
- Threads (and therefore OpenMP) are not available in Pyodide; builds requesting `-fopenmp` are rejected.

## pip in an Emscripten cross-platform environment

`pip` in an Emscripten cross-platform environment created by `xvenv` is replaced with a small wrapper that teaches pip about the `pyodide_<abi>_wasm32` and `pyemscripten_<abi>_wasm32` wheel platform tags, so that `pip install` can install wheels built for Pyodide. If pip is upgraded inside the environment, the wrapper is automatically reinstalled the next time `pip` is run.

This applies to the `pip` scripts in the environment's `bin` directory, and to `xpython -m pip`. Running `python -m pip` with the environment's build-platform interpreter uses pip's stock entry point, which only recognizes the `pyemscripten_<abi>_wasm32` tag (used by Pyodide 314.0 and later), and only if the installed pip vendors `packaging` 26.2 or later.

## `xpython`

In a cross-platform environment created from a Pyodide cross-build environment, `xvenv` links the Node-hosted Pyodide interpreter as `bin/xpython`. `xpython` runs code with that interpreter, against the environment's own `site-packages`; this requires `node` on your `PATH`.
