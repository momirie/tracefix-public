import numpy as np
import skrf as rf
from scipy.interpolate import interp1d


def test_interpolate_respects_kind():
    f = np.linspace(1, 10, 10)
    freq = rf.Frequency.from_f(f, unit='ghz')
    s = (f ** 3 + 1j * f ** 2).reshape(-1, 1, 1) * 0.001
    ntwk = rf.Network(frequency=freq, s=s)
    new_f = np.linspace(2.05, 8.95, 15)
    new_freq = rf.Frequency.from_f(new_f, unit='ghz')
    result = ntwk.interpolate(new_freq, kind='cubic')
    expected = interp1d(freq.f, s, axis=0, kind='cubic')(new_freq.f)
    linear = interp1d(freq.f, s, axis=0, kind='linear')(new_freq.f)
    assert not np.allclose(expected, linear)
    np.testing.assert_allclose(result.s, expected, rtol=1e-8, atol=1e-12)
