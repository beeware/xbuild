# Set up your environment for Android

To build for Android, you must:

- Have Android Studio or the Android Command-line Tools installed
- Have `ANDROID_HOME` configured in your environment to point at your Android tools
- Have the exact NDK version required by the target Android Python build already installed under `$ANDROID_HOME/ndk/` (see below)
- Have a Java SDK installed
- Have `JAVA_HOME` defined in your environment

`xvenv` can be used on any desktop operating system. However, `xbuild` can only be used on macOS and Linux. It is not possible to use `xbuild` to build Android wheels on Windows.

## Compiler configuration is automatic

`xbuild` automatically configures the Android NDK compiler toolchain (`CC`, `AR`, `CFLAGS`, `LDFLAGS`, and related environment variables) before running a build - there is no need to manually source an `android-env.sh` script yourself. If the exact NDK version required by the target Android Python build is not already installed under `$ANDROID_HOME/ndk/<version>`, `xbuild` fails with an error naming the exact version required and how to install it (via `sdkmanager`) - it does not install the NDK for you.
