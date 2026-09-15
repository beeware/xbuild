import pytest

from xvenv.versions import release, series, version

from ..utils import VersionInfo


@pytest.mark.parametrize(
    ("version_details", "version_str", "release_str", "series_str"),
    [
        (
            {
                "major": 3,
                "minor": 13,
                "micro": 10,
                "releaselevel": "final",
                "serial": 0,
            },
            "3.13.10",
            "3.13.10",
            "3.13",
        ),
        (
            {
                "major": 3,
                "minor": 14,
                "micro": 7,
                "releaselevel": "final",
                "serial": 0,
            },
            "3.14.7",
            "3.14.7",
            "3.14",
        ),
        (
            {
                "major": 3,
                "minor": 14,
                "micro": 0,
                "releaselevel": "candidate",
                "serial": 2,
            },
            "3.14.0rc2",
            "3.14.0",
            "3.14",
        ),
        (
            {
                "major": 3,
                "minor": 14,
                "micro": 0,
                "releaselevel": "beta",
                "serial": 2,
            },
            "3.14.0b2",
            "3.14.0",
            "3.14",
        ),
        (
            {
                "major": 3,
                "minor": 14,
                "micro": 0,
                "releaselevel": "alpha",
                "serial": 2,
            },
            "3.14.0a2",
            "3.14.0",
            "3.14",
        ),
    ],
)
def test_versions(version_details, version_str, release_str, series_str):
    v = VersionInfo(**version_details)
    assert version(v) == version_str
    assert release(v) == release_str
    assert series(v) == series_str
