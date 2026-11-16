import pathlib

import numpy as np

import healsparse


def test_read_pathlib_path(tmp_path):
    m = healsparse.HealSparseMap.make_empty(32, 256, np.float32)
    pixels = np.arange(100)
    m[pixels] = np.ones(pixels.size, dtype=np.float32)

    fname = tmp_path / "test_map.hs"
    assert isinstance(fname, pathlib.Path)
    m.write(str(fname), format="fits")

    m_str = healsparse.HealSparseMap.read(str(fname))
    m_path = healsparse.HealSparseMap.read(fname)

    assert m_path.nside_sparse == m_str.nside_sparse
    assert np.array_equal(m_path.valid_pixels, m_str.valid_pixels)
