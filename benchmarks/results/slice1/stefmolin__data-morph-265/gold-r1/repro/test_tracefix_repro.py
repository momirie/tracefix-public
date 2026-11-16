import numpy as np
import pandas as pd

from data_morph.data.dataset import Dataset
from data_morph.shapes.factory import ShapeFactory


def _dataset(xscale, yscale):
    rng = np.random.RandomState(0)
    df = pd.DataFrame({'x': rng.uniform(0, xscale, 50), 'y': rng.uniform(0, yscale, 50)})
    return Dataset(name='t', data=df)


def test_figure_eight_orientation():
    assert 'figure_eight' in ShapeFactory.AVAILABLE_SHAPES

    wide = ShapeFactory(_dataset(100, 20)).generate_shape('figure_eight')
    pts = np.array(wide.points)
    assert np.ptp(pts[:, 0]) > np.ptp(pts[:, 1])

    tall = ShapeFactory(_dataset(20, 100)).generate_shape('figure_eight')
    pts = np.array(tall.points)
    assert np.ptp(pts[:, 1]) > np.ptp(pts[:, 0])
