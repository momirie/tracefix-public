import json

import numcodecs
import numpy as np

import zarr


def test_v2_zstd_metadata_has_no_checksum_member(tmp_path):
    path = str(tmp_path / 'a.zarr')
    arr = zarr.create(
        shape=(10,),
        chunks=(5,),
        dtype='uint32',
        zarr_format=2,
        store=path,
        compressor=numcodecs.Zstd(level=1),
    )
    arr[:] = np.arange(10)
    with open(tmp_path / 'a.zarr' / '.zarray') as f:
        meta = json.load(f)
    assert meta['compressor']['id'] == 'zstd'
    assert 'checksum' not in meta['compressor']
