# Set up your environment for Emscripten

To build for Emscripten (Pyodide), you must:

- Have `git` and `bash` available (used to install the Emscripten SDK); and
- Have [Node](https://nodejs.org) 18 or later on your `PATH` (used by `xpython`, and by `meson`-based builds to run build-time checks).

`xvenv` can be used on any desktop operating system. However, `xbuild` can only be used on macOS and Linux. It is not possible to use `xbuild` to build Emscripten wheels on Windows.

Emscripten is supported for Python 3.12, 3.13 and 3.14.

## Customizing compilation

The compiler flags used for extension modules are derived from the configure-time flags of the target Python build. They can be overridden by setting `SIDE_MODULE_CFLAGS`, `SIDE_MODULE_CXXFLAGS` or `SIDE_MODULE_LDFLAGS` in your environment.

`meson`-based builds (e.g., `meson-python`) are given a [cross file](https://mesonbuild.com/Cross-compilation.html) describing the Emscripten target, which is written alongside the wrappers. Set `MESON_CROSS_FILE` to use your own cross file instead.

## Known limitations

- Rust extensions (`maturin`, `setuptools-rust`) are not supported: `cargo` is not wrapped, and the Rust tool chain for the `wasm32-unknown-emscripten` target is not configured.
- Fortran code is not supported.
- Threads (and therefore OpenMP) are not available in Pyodide; builds requesting `-fopenmp` are rejected.
