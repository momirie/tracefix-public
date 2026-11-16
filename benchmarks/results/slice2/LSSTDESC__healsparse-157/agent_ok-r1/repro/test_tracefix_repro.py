import numpy as np
import healsparse
from pathlib import Path


def test_read_pathlib_path(tmp_path):
    m = healsparse.HealSparseMap.make_empty(32, 256, np.float32)
    pix = np.arange(100, 200)
    m[pix] = np.ones(pix.size, dtype=np.float32)
    fname = Path(tmp_path) / 'test_map.hs'
    m.write(str(fname))

    m2 = healsparse.HealSparseMap.read(fname)
    np.testing.assert_array_equal(m2.valid_pixels, m.valid_pixels)
    np.testing.assert_array_almost_equal(m2[pix], m[pix])

    cov = healsparse.HealSparseCoverage.read(fname)
    assert cov.nside_coverage == 32
