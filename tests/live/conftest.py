# The nested pytest suites under _inner/ are meant to be collected only by
# the separate `pytest` invocations that test_cross_env.py runs inside each
# cross-venv's own interpreter.
collect_ignore = ["_inner"]
