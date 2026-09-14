# Release History

<!-- towncrier release notes start -->

## 0.2.0 (2025-09-10)

* Added `xbuild`, a PEP 517 build frontend that triggers cross-platform builds using a cross-platform virtual environment created by `xvenv`. Build requirements are installed for the build platform by default, unless listed in a new `target-requires` key in `build-system`, in which case they're installed for the target platform.

## 0.0.1 (2025-09-05)

Initial release.

* Includes `xvenv`, a tool for creating cross platform environments. This has undergone initial testing to verify it works for iOS, Android and Emscripten environments. The created environment is sufficient to trick `pip` into installing binaries for the target platform into the environment; and for tools like `wheel` to trigger builds with compiler invocations derived from `sysconfgdata`. This won't generally result in a *successful* build, as there will usually be other environmental requirements; but the a cross-platform build will be attempted.
