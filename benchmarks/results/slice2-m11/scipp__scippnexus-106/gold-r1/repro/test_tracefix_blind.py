import h5py
import numpy as np
import pytest
import scipp as sc

from scippnexus import NXroot, NXentry


@pytest.fixture()
def nxroot():
    with h5py.File('dummy_tf.nxs', mode='w', driver='core', backing_store=False) as f:
        yield NXroot(f)


def test_loading_nxtransformations_group_gives_spatial_dtype_variables(nxroot):
    from scippnexus import NXtransformations
    entry = nxroot.create_class('entry', NXentry)
    tf = entry.create_class('transformations', NXtransformations)
    t = tf.create_field('t1', sc.scalar(2.0, unit='m'))
    t.attrs['transformation_type'] = 'translation'
    t.attrs['vector'] = np.array([0.0, 0.0, 1.0])
    t.attrs['depends_on'] = '.'
    loaded = tf[()]
    assert loaded['t1'].dtype == sc.DType.translation3
