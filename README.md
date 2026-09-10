# xbuild

[![Python Versions](https://img.shields.io/pypi/pyversions/xbuild.svg)](https://pypi.python.org/pypi/xbuild) [![PyPI Version](https://img.shields.io/pypi/v/xbuild.svg)](https://pypi.python.org/pypi/xbuild) [![Maturity](https://img.shields.io/pypi/status/xbuild.svg)](https://pypi.python.org/pypi/xbuild) [![BSD License](https://img.shields.io/pypi/l/xbuild.svg)](https://github.com/beeware/xbuild/blob/master/LICENSE) [![Discord server](https://img.shields.io/discord/836455665257021440?label=Discord%20Chat&logo=discord&style=plastic)](https://beeware.org/bee/chat/)

`xbuild` is [PEP 517](https://peps.python.org/0517) build frontend that has additions and extensions to support cross-compiling wheels for platforms where compilation cannot be performed natively - most notably:

- Android
- Emscripten (WASM)
- iOS

## Quickstart

### xbuild

Create a virtual environment for your build platform (i.e., the platform where you will be compiling), and install `xbuild`. Then, run `xbuild` from the root directory of the project you want to build. You *must* pass in the `--sysconfig` argument, providing the path to the `sysconfig_vars` JSON file for the target platform, or the equivalent `sysconfigdata` python configuration:

```console
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ python -m pip install xbuild
(venv) $ python -m xbuild --sysconfig path/to/_sysconfig_vars__...json
```

This will do the equivalent of `python -m build`, but in an cross-platform environment that is pretending to be the environment described by the sysconfig data that has been provided.

### xvenv

To explicitly create a cross-platform virtual environment, start by creating a virtual environment for your build platform (i.e., the platform where you will be compiling), then install and use the `xvenv` script to create cross-platform virtual environment.

```console
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ python -m pip install xbuild
(venv) $ python -m xvenv --sysconfig path/to/_sysconfig_vars__...json x-venv
```

You can then activate and deactivate the `x-venv` environment as you would any other virtual environment.

## Documentation

Documentation for Toga Chart can be found on [Read The Docs](https://toga-chart.readthedocs.io).

## Community

`xbuild` is part of the [BeeWare suite](http://beeware.org). You can talk to the community through:

- [@pybeeware on Twitter](https://twitter.com/pybeeware)
- [Discord](https://beeware.org/bee/chat/)

We foster a welcoming and respectful community as described in our [BeeWare Community Code of Conduct](http://beeware.org/community/behavior/).

## Contributing

If you experience problems with `xbuild`, [log them on GitHub](https://github.com/beeware/xbuild/issues). If you want to contribute code, please [fork the code](https://github.com/beeware/xbuild) and [submit a pull request](https://github.com/beeware/xbuild/pulls).
