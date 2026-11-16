import numpy as np
import ocbpy


class _Sub(object):
    def __init__(self, records):
        self.records = records
        self.rec_ind = 0


def test_dual_boundary_rec_ind_out_of_range_pair():
    # Build a DualBoundary-like object without loading data files
    dual = ocbpy.DualBoundary.__new__(ocbpy.DualBoundary)
    dual.ocb = _Sub(5)
    dual.eab = _Sub(5)
    dual.ocb_ind = np.array([0, 1, 2])
    dual.eab_ind = np.array([0, 1, 9])  # bad EAB index outside data range
    dual.dtime = np.array([0, 1, 2])
    dual.records = 3

    dual.rec_ind = 2

    assert dual.eab.rec_ind <= dual.eab.records
    assert dual.ocb.rec_ind == 2
