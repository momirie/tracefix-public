import h5py
import scipp as sc

import scippnexus as snx
from scippnexus import nexus_classes  # noqa: F401


def test_nxtransformations_loaded_as_spatial_variable(tmp_path):
    path = tmp_path / 'f.nxs'
    with h5py.File(path, mode='w') as f:
        g = f.create_group('entry')
        g.attrs['NX_class'] = 'NXentry'
        t = g.create_group('transformations')
        t.attrs['NX_class'] = 'NXtransformations'
        ds = t.create_dataset('t1', data=2.0)
        ds.attrs['units'] = 'm'
        ds.attrs['transformation_type'] = 'translation'
        ds.attrs['vector'] = [0.0, 0.0, 1.0]
        ds.attrs['depends_on'] = '.'
    with snx.File(path) as root:
        loaded = root['entry']['transformations'][()]
        value = loaded['t1']
        assert isinstance(value, sc.Variable)
        assert value.dtype == sc.DType.translation3
