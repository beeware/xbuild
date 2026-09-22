# Environment variables

## `XBUILD_CACHE`

The directory used to cache downloaded target-platform Python builds when using `--platform`. Overridden by the `--cache` command-line option, which takes precedence. If neither is set, defaults to a platform-appropriate user cache directory (via [`platformdirs.user_cache_dir("xbuild")`](https://pypi.org/project/platformdirs/)).

## `XBUILD_ENV`

Controls whether an active cross-platform virtual environment's patches (to `sys`, `os`, `platform`, and `sysconfig` - see [How it works](../topics/how-it-works.md)) are applied. Set to `off` to temporarily make an active cross-platform environment behave like a normal build-platform environment:

```console
$ source x-venv/bin/activate
(x-venv) $ python -c "import sys; print(sys.platform)"
ios
(x-venv) $ XBUILD_ENV=off python -c "import sys; print(sys.platform)"
darwin
```

Any value other than `off` (or unsetting the variable entirely) leaves the cross-platform patches active - this is the default behavior for any activated cross-venv.
