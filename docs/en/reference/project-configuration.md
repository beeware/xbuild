# Project configuration

xbuild extends the standard [PEP 517](https://peps.python.org/0517) `[build-system]` table in `pyproject.toml` with one additional key.

## `target-requires`

Standard PEP 517 `requires` lists dependencies that are installed **for the build platform** - the platform where compilation is happening. For example, if you're compiling on macOS for an ARM64 iOS simulator, and your project lists `ninja` in `requires`, the *macOS* version of `ninja` is installed, because `ninja` needs to run during the build itself.

If your build backend also needs a dependency that must be installed **for the target platform** - for example, a Python package with a compiled extension that gets linked against during the build - list it under `target-requires` instead:

```toml
[build-system]
requires = ["setuptools"]
target-requires = ["target-tool"]
build-backend = "setuptools.build_meta"
```

In this example, the *macOS* version of `setuptools` is installed (needed to run the build backend), while the *iOS* version of `target-tool` is installed into the cross-platform build environment.

`target-requires` is only meaningful for isolated builds (the default; see [`--no-isolation`](./commands/xbuild.md#-no-isolation-n-vs-installer-name)). It is ignored when installing dependencies in an already-active environment.
