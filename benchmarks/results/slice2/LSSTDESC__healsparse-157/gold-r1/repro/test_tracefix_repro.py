import pathlib

import numpy as np
import numpy.testing as testing

import healsparse


def test_read_pathlib_path(tmp_path):
    nside_coverage = 32
    nside_sparse = 256
    m = healsparse.HealSparseMap.make_empty(nside_coverage, nside_sparse, np.float32)
    pixels = np.arange(100)
    m[pixels] = np.ones(pixels.size, dtype=np.float32)

    fname = tmp_path / "test_map.hs"
    assert isinstance(fname, pathlib.Path)
    m.write(str(fname))

    m2 = healsparse.HealSparseMap.read(fname)

    testing.assert_array_equal(m2.valid_pixels, m.valid_pixels)
    testing.assert_array_almost_equal(m2[pixels], m[pixels])
