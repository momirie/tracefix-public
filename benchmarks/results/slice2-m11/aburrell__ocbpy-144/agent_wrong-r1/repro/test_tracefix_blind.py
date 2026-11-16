import datetime as dt

import ocbpy


def test_dual_boundary_pairs_in_range():
    stime = dt.datetime(2002, 10, 31, 19, 0, 0)
    etime = dt.datetime(2002, 10, 31, 21, 0, 0)
    dual = ocbpy.DualBoundary(stime=stime, etime=etime, hemisphere=1)

    assert dual.records > 0
    for o, e in zip(dual.ocb_ind, dual.eab_ind):
        assert 0 <= o < dual.ocb.records
        assert 0 <= e < dual.eab.records
