# Set up your environment for Android

To build for Android, you must:

- Have Android Studio or the Android Command-line Tools installed
- Have `ANDROID_HOME` configured in your environment to point at your Android tools
- Have a Java SDK installed
- Have `JAVA_HOME` defined in your environment

`xvenv` can be used on any desktop operating system. However, `xbuild` can only be used on macOS and Linux. It is not possible to use `xbuild` to build Android wheels on Windows.

## Compiler configuration is automatic

`xbuild` automatically configures the Android NDK compiler tool chain (`CC`, `AR`, `CFLAGS`, `LDFLAGS`, and related environment variables) before running a build - there is no need to do this manually yourself. If the exact NDK version required by the target Android Python build is not already installed under `$ANDROID_HOME/ndk/<version>`, it is installed automatically via `sdkmanager`, which may take several minutes and requires network access the first time a given NDK version is needed.
