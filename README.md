# xbuild

[![Python Versions](https://img.shields.io/pypi/pyversions/xbuild.svg)](https://pypi.python.org/pypi/xbuild)
[![PyPI Version](https://img.shields.io/pypi/v/xbuild.svg)](https://pypi.python.org/pypi/xbuild)
[![Maturity](https://img.shields.io/pypi/status/xbuild.svg)](https://pypi.python.org/pypi/xbuild)
[![BSD License](https://img.shields.io/pypi/l/xbuild.svg)](https://github.com/beeware/xbuild/blob/master/LICENSE)
[![Discord server](https://img.shields.io/discord/836455665257021440?label=Discord%20Chat&logo=discord&style=plastic)](https://beeware.org/bee/chat/)

`xbuild` is PEP517 build backend that has additions and extensions to support cross-compiling wheels for platforms where compilation cannot be performed natively - most notably:

* Android
* Emscripten (WASM)
* iOS

## Usage

### Creating a cross virtual environment

To create a cross virtual environment:

    $ python3 -m venv venv
    $ source venv/bin/activate
    (venv) $ pip install xbuild
    (venv) $ python -m venv x-venv
    (venv) $ xvenv --sysconfig path/to/_sysconfig_vars__.json x-venv
    (venv) $ deactivate
    $ source x-venv/bin/activate
    (x-venv) python -c "import sys; print(sys.platform)"

This should now print the platform identifier for the target platform, not your
build platform.

## Contributing

To set up a development environment:

    $ python3 -m venv venv
    $ source venv/bin/activate
    (venv) $ python -m pip install -U pip
    (venv) $ python -m pip install -e . --group dev

## Community

`xbuild` is part of the [BeeWare suite](http://beeware.org). You can talk to the
community through:

- [@pybeeware on Twitter](https://twitter.com/pybeeware)
- [Discord](https://beeware.org/bee/chat/)

We foster a welcoming and respectful community as described in our [BeeWare
Community Code of Conduct](http://beeware.org/community/behavior/).

## Contributing

If you experience problems with `xbuild`, [log them on
GitHub](https://github.com/beeware/xbuild/issues). If you want to contribute
code, please [fork the code](https://github.com/beeware/xbuild) and [submit a
pull request](https://github.com/beeware/xbuild/pulls).
