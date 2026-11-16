import numpy as np
import unyt
from unyt import unyt_array


def test_mean_non_base_unit_no_recursion():
    a = unyt_array([1, 2, 3], unyt.Msun)
    m = a.mean()
    assert m.units.dimensions == unyt.kg.units.dimensions
    assert np.isclose(float(m.to("Msun").value), 2.0)
