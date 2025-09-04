# Changelog

## 0.0.1 (5 Sep 2025)

Initial release.

Includes `xvenv`, a tool for creating cross platform environments. This has undergone initial testing to verify it works for iOS, Android and Emscripten environments. The created environment is sufficient to trick `pip` into installing binaries for the target platform into the environment; and for tools like `wheel` to trigger builds with compiler invocations derived from `sysconfgdata`. This won't generally result in a *successful* build, as there will usually be other environmental requirements; but the a cross-platform build will be attempted.
