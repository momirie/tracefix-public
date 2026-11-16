import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import mplotutils as mpu
from mplotutils.tests import subplots_context


def test_colorbar_does_not_change_gca():
    with subplots_context() as (f, ax):
        h = ax.pcolormesh([[0, 1], [1, 2]])
        assert plt.gca() is ax

        cbar = mpu.colorbar(h, ax)

        assert plt.gca() is ax
        assert plt.gca() is not cbar.ax
