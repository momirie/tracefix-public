import numpy as np
import scipp as sc

import plopp as pp


def test_plot_datetime_bin_edges_with_variances():
    time = sc.array(dims=['time'],
                    values=np.arange(np.datetime64('2017-03-16T20:58:17'),
                                     np.datetime64('2017-03-16T21:15:17'), 10))
    v = np.random.RandomState(0).rand(time.sizes['time'] - 1)
    da = sc.DataArray(data=sc.array(dims=['time'], values=10 * v, variances=v),
                      coords={'time': time})
    fig = pp.plot(da)
    assert fig is not None
