import pathlib

import numpy as np
import numpy.testing as testing

import healsparse


def test_read_pathlib_path_fits(tmp_path):
    m = healsparse.HealSparseMap.make_empty(32, 256, np.float32)
    pixels = np.arange(100)
    m[pixels] = np.ones(pixels.size, dtype=np.float32)

    fname = tmp_path / 'test_map.hs'
    assert isinstance(fname, pathlib.Path)
    m.write(str(fname), format='fits')

    m_path = healsparse.HealSparseMap.read(fname)
    testing.assert_array_equal(m_path.valid_pixels, m.valid_pixels)

    cov = healsparse.HealSparseCoverage.read(fname)
    assert cov.nside_coverage == 32
