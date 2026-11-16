import h5py
import numpy as np
import pytest
import scipp as sc

import scippnexus as snx
from scippnexus import NXroot


@pytest.fixture()
def nxroot():
    with h5py.File('dummy.nxs', mode='w', driver="core", backing_store=False) as f:
        yield NXroot(f)


def test_nxtransformations_loads_translation_as_spatial_variable(nxroot):
    entry = nxroot.create_class('entry', snx.NXentry)
    transformations = entry.create_class('transformations', snx.NXtransformations)
    value = sc.scalar(2.0, unit='m')
    t = transformations.create_field('t1', value)
    t.attrs['depends_on'] = '.'
    t.attrs['transformation_type'] = 'translation'
    t.attrs['offset'] = np.array([0.0, 0.0, 0.0])
    t.attrs['offset_units'] = 'm'
    t.attrs['vector'] = np.array([0.0, 0.0, 1.0])
    loaded = nxroot['entry/transformations'][()]
    result = loaded['t1']
    assert isinstance(result, sc.Variable)
    assert result.dtype == sc.DType.translation3
