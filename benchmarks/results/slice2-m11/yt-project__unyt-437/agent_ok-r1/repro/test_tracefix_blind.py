import pytest

from unyt import unyt_array


def test_dimensionless_to_astropy():
    astropy = pytest.importorskip("astropy")
    x = unyt_array([1, 2, 3], "kpc")
    y = unyt_array([1, 1, 1], "kpc")
    z = x / y
    q = z.to_astropy()
    assert q.unit.is_equivalent(astropy.units.dimensionless_unscaled)
    assert list(q.value) == [1, 2, 3]
