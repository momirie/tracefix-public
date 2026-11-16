import h5py
import pytest
import scipp as sc

from scippnexus import NXentry, NXroot


@pytest.fixture()
def nxroot():
    with h5py.File('dummy_tf.nxs', mode='w', driver="core", backing_store=False) as f:
        yield NXroot(f)


def test_loading_nxtransformations_gives_spatial_dtypes(nxroot):
    entry = nxroot.create_class('entry', NXentry)
    f = entry._group
    tf = f.create_group('transformations')
    tf.attrs['NX_class'] = 'NXtransformations'
    t = tf.create_dataset('t1', data=2.0)
    t.attrs['depends_on'] = '.'
    t.attrs['transformation_type'] = 'translation'
    t.attrs['units'] = 'm'
    t.attrs['vector'] = [0.0, 0.0, 1.0]
    loaded = nxroot['entry/transformations'][()]
    assert loaded['t1'].dtype == sc.DType.translation3
