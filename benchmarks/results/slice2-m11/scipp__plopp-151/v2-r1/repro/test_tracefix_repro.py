import numpy as np
import scipp as sc

from plopp.backends.matplotlib.line import Line


def test_make_data_datetime_bin_edges_with_variances():
    time = sc.array(dims=['time'],
                    values=np.arange(np.datetime64('2017-03-16T20:58:17'),
                                     np.datetime64('2017-03-16T21:15:17'), 10))
    v = np.arange(1.0, time.sizes['time'])
    da = sc.DataArray(data=sc.array(dims=['time'], values=10 * v, variances=v),
                      coords={'time': time})
    line = Line.__new__(Line)
    line._data = da
    line._dim = 'time'
    # Computing bin centres for the error bars must not raise for datetimes
    line._make_data()
