# Set up your environment for iOS

You must have Xcode installed, with the iOS SDK added.

It is also strongly advised that you:

- Add the path to the iOS binary shims to your path. These are provided in the `Python.xcframework/ios-arm64/bin` and `Python.xcframework/ios-arm64_x86_64-simulator/bin` folder for the iOS support package that you have downloaded.

- Clear your path of any other dependencies. It is very easy for macOS ARM64 binaries from Homebrew and other sources to leak into iOS builds if they are present on the path; the safest approach is to set your path so it only contains:
    - The path for the Python binary (ideally, your virtual environment's `bin` directory)
    - `/usr/bin`
    - `/bin`
    - `/usr/sbin`
    - `/sbin`
    - `/Library/Apple/usr/bin`
