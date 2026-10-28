import sys

import pytest

from xvenv.args import MISSING_CONFIG_ERROR, make_common_parser, parse_common_args


@pytest.fixture
def parser():
    return make_common_parser("test", description="Test", version="test 1.0")


@pytest.fixture(autouse=True)
def native_env(monkeypatch):
    monkeypatch.delattr(sys, "cross_compiling", raising=False)


def test_config_required_by_default(parser, capsys):
    """By default, a configuration source is required outside a cross env."""
    with pytest.raises(SystemExit) as excinfo:
        parse_common_args(parser, [])

    assert excinfo.value.code == 2
    assert MISSING_CONFIG_ERROR in capsys.readouterr().err


def test_config_not_required(parser):
    """With require_config=False, a missing configuration source isn't an
    error, but use_current_env is still reported."""
    args = parse_common_args(parser, [], require_config=False)

    assert args.use_current_env is True


def test_config_not_required_with_platform(parser):
    """With require_config=False, an explicit platform is still parsed."""
    args = parse_common_args(parser, ["--platform", "ios"], require_config=False)

    assert args.use_current_env is False
    assert args.platform == "ios"
