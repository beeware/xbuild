# The nested pytest suites under _inner/ are meant to be collected only by
# the separate `pytest` invocations that test_cross_env.py runs inside each
# cross-venv's own interpreter (see _run_inner_suite() below) — never by the
# outer `pytest tests` run itself, which uses a different Python and would
# see a completely different sys.platform / expected-values shape.
collect_ignore = ["_inner"]
