import numpy as np
import zarr
from zarr.core.buffer import default_buffer_prototype
from zarr.core.sync import sync


def test_consolidated_metadata_nan_fill_value_serialized_as_string():
    store = zarr.storage.MemoryStore()
    root = zarr.group(store, zarr_format=2)
    root.create_array("time", shape=(12,), dtype=np.float64, fill_value=np.nan)
    zarr.consolidate_metadata(store)
    buf = sync(store.get(".zmetadata", prototype=default_buffer_prototype()))
    text = buf.to_bytes().decode()
    assert '"fill_value": "NaN"' in text
    assert '"fill_value": NaN' not in text
