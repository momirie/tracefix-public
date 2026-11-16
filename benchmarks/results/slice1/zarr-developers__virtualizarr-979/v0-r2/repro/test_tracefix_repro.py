from virtualizarr.parsers.kerchunk.translator import manifest_from_kerchunk_chunk_dict


def test_inlined_string_chunk_is_read():
    manifest = manifest_from_kerchunk_chunk_dict({"0": "hello"}, shape=(1,))
    assert manifest is not None
    assert len(manifest.dict()) == 1
