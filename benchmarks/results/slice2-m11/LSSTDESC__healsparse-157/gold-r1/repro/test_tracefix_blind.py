import pathlib

import numpy as np

import healsparse


def test_read_pathlib_path(tmp_path):
    nside_coverage = 32
    nside_sparse = 256
    hsp_map = healsparse.HealSparseMap.make_empty(nside_coverage, nside_sparse, np.float32)
    hsp_map[0:100] = 1.0

    fname = tmp_path / "map.hs"
    assert isinstance(fname, pathlib.Path)
    hsp_map.write(str(fname), clobber=True)

    read_map = healsparse.HealSparseMap.read(fname)
    assert read_map.nside_sparse == nside_sparse
    np.testing.assert_array_equal(read_map.valid_pixels, hsp_map.valid_pixels)
