import h5py
import numpy as np
import scipp as sc

from scippnexus import NXroot, NXentry
from scippnexus.nexus_classes import NXtransformations


def test_nxtransformations_loads_as_spatial_variables():
    with h5py.File('dummy.nxs', mode='w', driver="core", backing_store=False) as f:
        root = NXroot(f)
        entry = root.create_class('entry', NXentry)
        t = entry.create_class('transformations', NXtransformations)
        ds = t._group.create_dataset('t1', data=np.array(2.0))
        ds.attrs['depends_on'] = '.'
        ds.attrs['transformation_type'] = 'translation'
        ds.attrs['offset'] = np.array([0.0, 0.0, 0.0])
        ds.attrs['vector'] = np.array([0.0, 0.0, 1.0])
        ds.attrs['units'] = 'm'
        loaded = root['entry/transformations'][()]
        value = loaded['t1']
        assert isinstance(value, sc.Variable)
        assert value.dtype == sc.DType.translation3
