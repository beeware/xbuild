# How to run a build

[`xbuild`](../reference/commands/xbuild.md) builds a wheel for a target platform, in an isolated cross-platform virtual environment, by default.

Before you start, make sure your build-platform machine is set up for your chosen target platform - see [Platform setup](platform-setup/index.md).

## A basic build

From the root directory of the project you want to build, providing the platform and architecture you want to target:

```console
(venv) $ xbuild --platform ios --arch arm64-iphonesimulator
```

This creates an isolated cross-platform virtual environment, and triggers a PEP 517 build inside it. Any build `requires` are installed *for the build platform*. For example, if you're running on macOS, building for an ARM64 iPhone simulator, and your project lists `ninja` as a requirement, the *macOS* version of `ninja` is installed - this ensures the binary is executable during the build.

## Installing target-platform build dependencies

If your build backend needs a dependency installed *for the target platform* rather than the build platform, declare it under `target-requires` in your `build-system` table:

```toml
[build-system]
requires = ["setuptools"]
target-requires = ["target-tool"]
build-backend = "setuptools.build_meta"
```

See [Project configuration](../reference/project-configuration.md#target-requires) for the full reference.

## Choosing an installer

By default, dependencies are installed into the isolated build environment with `pip`. Use `--installer` to choose a different one:

```console
(venv) $ xbuild --platform ios --arch arm64-iphonesimulator --installer uv
```

## Passing settings to the build backend

Use `--config-setting KEY=VALUE` (repeatable) or `--config-json` to pass settings through to the build backend - see the [xbuild reference](../reference/commands/xbuild.md#-config-setting-keyvalue-c-keyvalue-vs-config-json-json_string) for the full syntax, including how to pass hyphen-prefixed values.

## Reusing an active cross-venv

If you already have an active cross-platform virtual environment (created with [`xvenv`](../reference/commands/xvenv.md) - see [How to create a cross-platform venv](create-cross-venv.md)), you don't need to provide `--platform`/`--build-details`/`--sysconfig` at all - the configuration of your active cross-venv is copied into the isolated build environment automatically.

You can also skip creating an isolated build environment entirely, and build directly inside your active cross-venv, with `--no-isolation`:

```console
(x-venv) $ xbuild --no-isolation
```

When using `--no-isolation`, you're responsible for ensuring all of the project's build dependencies (including anything listed in `target-requires`) are already installed in the active environment.
