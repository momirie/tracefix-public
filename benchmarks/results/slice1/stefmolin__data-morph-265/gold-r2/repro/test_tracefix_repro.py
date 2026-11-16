import numpy as np

from data_morph.data.loader import DataLoader
from data_morph.shapes.factory import ShapeFactory


def _points(shape):
    return np.array(shape.points)


def test_figure_eight_available_and_orientation():
    dataset = DataLoader.load_dataset('dino')
    shape = ShapeFactory(dataset).generate_shape('figure_eight')
    pts = _points(shape)
    x_range, y_range = dataset.data_bounds.range
    pts_range = pts.max(axis=0) - pts.min(axis=0)
    if x_range >= y_range:
        assert pts_range[0] > pts_range[1]
    else:
        assert pts_range[1] > pts_range[0]


def test_figure_eight_vertical_for_tall_data():
    dataset = DataLoader.load_dataset('panda')
    x_range, y_range = dataset.data_bounds.range
    shape = ShapeFactory(dataset).generate_shape('figure_eight')
    pts = _points(shape)
    pts_range = pts.max(axis=0) - pts.min(axis=0)
    assert (pts_range[0] > pts_range[1]) == (x_range >= y_range)
