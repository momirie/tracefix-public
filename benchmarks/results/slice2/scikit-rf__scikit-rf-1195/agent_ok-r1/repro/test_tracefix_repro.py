import numpy as np
import skrf as rf


def test_interpolate_respects_kind():
    freq = rf.Frequency.from_f(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), unit='ghz')
    s = (np.array([0.0, 1.0, 4.0, 9.0, 16.0]) / 20.0).reshape(-1, 1, 1).astype(complex)
    ntwk = rf.Network(frequency=freq, s=s, z0=50)
    new_f = rf.Frequency.from_f(np.array([2.5]), unit='ghz')
    lin = ntwk.interpolate(new_f, kind='linear').s[0, 0, 0]
    quad = ntwk.interpolate(new_f, kind='quadratic').s[0, 0, 0]
    # linear between 1 and 4 -> 2.5 ; quadratic exact -> 2.25
    assert np.isclose(lin, 2.5 / 20.0)
    assert np.isclose(quad, 2.25 / 20.0)
