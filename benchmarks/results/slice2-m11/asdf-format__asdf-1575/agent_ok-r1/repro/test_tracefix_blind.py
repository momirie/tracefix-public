import gc
import weakref

import numpy as np

import asdf


def test_closed_file_does_not_hold_tree_references(tmp_path):
    fn = str(tmp_path / "test.asdf")
    asdf.AsdfFile({"arr": np.arange(1000)}).write_to(fn)

    with asdf.open(fn, copy_arrays=True, lazy_load=False) as af:
        array_ref = weakref.ref(af["arr"])

    gc.collect()
    assert array_ref() is None
