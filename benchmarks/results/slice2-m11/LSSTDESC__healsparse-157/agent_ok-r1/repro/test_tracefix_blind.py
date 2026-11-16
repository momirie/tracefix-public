import pathlib

import numpy as np

import healsparse


def test_read_pathlib_path(tmp_path):
    nside_coverage = 32
    nside_sparse = 128
    m = healsparse.HealSparseMap.make_empty(nside_coverage, nside_sparse, np.float32)
    m[0:100] = np.arange(100, dtype=np.float32)

    fname = pathlib.Path(tmp_path) / 'test_map.hs'
    m.write(str(fname))

    m2 = healsparse.HealSparseMap.read(fname)

    np.testing.assert_array_equal(m2.valid_pixels, m.valid_pixels)
    np.testing.assert_array_equal(m2[0:100], m[0:100])
