from virtualizarr.parsers.kerchunk.translator import manifest_from_kerchunk_chunk_dict


def test_inlined_chunk_refs_are_read():
    chunk_dict = {"0": "base64:AQIDBA==", "1": "hello"}
    manifest = manifest_from_kerchunk_chunk_dict(chunk_dict, shape=(2,))
    entries = manifest.dict()
    assert len(entries) == 2
