from importlib.metadata import version

# The version number for xvenv is the same as the underlying package
__version__ = version("xbuild")

__all__ = ["__version__"]
