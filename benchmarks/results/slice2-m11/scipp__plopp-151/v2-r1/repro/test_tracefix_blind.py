import numpy as np
import scipp as sc

import plopp as pp


def _make_da():
    time = sc.array(dims=['time'],
                    values=np.arange(np.datetime64('2017-03-16T20:58:17'),
                                     np.datetime64('2017-03-16T21:15:17'), 10))
    v = np.arange(1, time.sizes['time'], dtype='float64')
    return sc.DataArray(data=sc.array(dims=['time'], values=10 * v, variances=v),
                        coords={'time': time})


def test_plot_datetime_bin_edges_with_variances_matplotlib():
    da = _make_da()
    pp.plot(da)


def test_plot_datetime_bin_edges_with_variances_plotly():
    da = _make_da()
    pp.plot(da, backend='plotly')
