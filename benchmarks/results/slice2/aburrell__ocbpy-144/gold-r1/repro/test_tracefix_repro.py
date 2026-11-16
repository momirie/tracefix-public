import datetime as dt

import numpy as np

import ocbpy


def test_dual_boundary_no_eab_index_out_of_range():
    stime = dt.datetime(2000, 1, 1)
    etime = dt.datetime(2000, 7, 1)
    dual = ocbpy.DualBoundary(stime=stime, etime=etime, hemisphere=1)
    eab = dual.eab
    assert eab.records > 10
    assert dual.ocb.records > 10

    # Limit the EAB data range so OCB data extends beyond it
    nrec = eab.records // 2
    eab.records = nrec

    dual.set_good_ind()

    assert len(dual.eab_ind) > 0
    assert np.all(np.asarray(dual.eab_ind) < nrec)
    assert np.all(np.asarray(dual.ocb_ind) < dual.ocb.records)
