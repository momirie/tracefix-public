from virtualizarr.parsers.kerchunk.translator import manifest_from_kerchunk_chunk_dict


def test_inlined_chunk_reading_supported():
    manifest = manifest_from_kerchunk_chunk_dict(
        {"0": "base64:AQIDBA=="}, shape=(1,)
    )
    assert len(manifest.dict()) == 1
    entry = manifest.dict()["0"]
    assert entry["length"] == 4
