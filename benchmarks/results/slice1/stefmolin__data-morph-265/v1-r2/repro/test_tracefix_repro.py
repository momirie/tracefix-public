import numpy as np

from data_morph.data.loader import DataLoader
from data_morph.shapes import points


def test_figure_eight_orientation_follows_data():
    shape_cls = getattr(points, 'FigureEight', None)
    assert shape_cls is not None, 'figure eight shape is not available'

    for name in ('dino', 'panda'):
        dataset = DataLoader.load_dataset(name)
        shape = shape_cls(dataset)
        pts = np.array(shape.points)
        sx = np.ptp(pts[:, 0])
        sy = np.ptp(pts[:, 1])
        dx, dy = dataset.data_bounds.range
        if dx >= dy:
            assert sx > sy
        else:
            assert sy > sx
        cx, cy = dataset.data_bounds.center
        assert abs(pts[:, 0].mean() - cx) < 0.05 * dx
        assert abs(pts[:, 1].mean() - cy) < 0.05 * dy
