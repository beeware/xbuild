# The nested pytest suites under samples are part of the sample project that
# are built by xbuild and tested with xpython, rather than being part of
# xbuild's own test suite.
collect_ignore = ["samples"]
