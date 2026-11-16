import numpy as np
import skrf as rf
from scipy.interpolate import interp1d


def test_interpolate_respects_kind():
    freq = rf.Frequency(1, 10, 10, 'ghz')
    f = freq.f
    s = (np.sin(f / 1e9) + 1j * np.cos(f / 2e9)).reshape(-1, 1, 1)
    ntwk = rf.Network(frequency=freq, s=s, z0=50)
    new_freq = rf.Frequency(1, 10, 37, 'ghz')
    expected = interp1d(f, s, axis=0, kind='cubic')(new_freq.f)
    got = ntwk.interpolate(new_freq, kind='cubic').s
    assert np.allclose(got, expected)
