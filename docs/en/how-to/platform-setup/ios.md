# Set up your environment for iOS

You must have a machine running macOS, with Xcode installed, and the iOS SDK added.

## PATH configuration is automatic

`xbuild` automatically configures `PATH` before running a build, so that the correct target-platform `clang`/`ar`/`strip` shims are used for compilation, and no build-machine-native tools (e.g. Homebrew binaries) leak into the build. There is no need to manually add the iOS binary shims to your path, or manually clear your path of other dependencies, before running `xbuild`.
