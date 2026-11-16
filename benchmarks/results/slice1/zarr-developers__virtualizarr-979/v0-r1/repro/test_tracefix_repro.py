from virtualizarr.parsers.kerchunk.translator import manifest_from_kerchunk_chunk_dict


def test_inlined_kerchunk_chunk_is_read():
    chunks = {"0": "hello", "1": ["s3://bucket/file.nc", 10, 20]}
    manifest = manifest_from_kerchunk_chunk_dict(chunks, shape=(2,))
    entries = manifest.dict()
    assert len(entries) == 2
    assert entries["1"]["offset"] == 10
    assert entries["1"]["length"] == 20
