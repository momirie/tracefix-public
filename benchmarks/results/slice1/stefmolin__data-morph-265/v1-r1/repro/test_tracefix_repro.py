import importlib

import numpy as np
import pandas as pd

from data_morph.data.dataset import Dataset


def _make(xr, yr):
    rng = np.random.default_rng(0)
    df = pd.DataFrame({'x': rng.uniform(0, xr, 50), 'y': rng.uniform(0, yr, 50)})
    df.loc[0, ['x', 'y']] = [0, 0]
    df.loc[1, ['x', 'y']] = [xr, yr]
    return Dataset('t', df)


def test_figure_eight_orientation():
    points_mod = importlib.import_module('data_morph.shapes.points')
    figure_eight = points_mod.FigureEight

    pts = np.array(figure_eight(_make(100, 20)).points)
    assert np.ptp(pts[:, 0]) > np.ptp(pts[:, 1])

    pts = np.array(figure_eight(_make(20, 100)).points)
    assert np.ptp(pts[:, 1]) > np.ptp(pts[:, 0])
