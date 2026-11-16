import datetime as dt
import threading

import ocbpy


def test_dual_boundary_no_bad_pair():
    stime = dt.datetime(2002, 10, 31)
    etime = dt.datetime(2002, 12, 1)
    out = {}

    def build():
        try:
            out['dual'] = ocbpy.DualBoundary(stime=stime, etime=etime,
                                             hemisphere=1)
        except Exception as err:
            out['err'] = err

    th = threading.Thread(target=build, daemon=True)
    th.start()
    th.join(60)
    assert not th.is_alive(), 'DualBoundary construction did not terminate'
    assert 'err' not in out, repr(out.get('err'))
    dual = out['dual']
    assert dual.records > 0
    assert len(dual.eab_ind) == dual.records
    assert (dual.eab_ind < dual.eab.records).all()
    assert (dual.ocb_ind < dual.ocb.records).all()
    assert (dual.eab_ind >= 0).all()
