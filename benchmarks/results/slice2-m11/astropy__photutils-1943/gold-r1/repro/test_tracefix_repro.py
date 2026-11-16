import warnings

import numpy as np

from photutils.detection import IRAFStarFinder


def test_iraf_exclude_border_all_sources_on_border():
    yy, xx = np.mgrid[0:50, 0:50]
    data = 100.0 * np.exp(-((xx - 1) ** 2 + (yy - 25) ** 2) / (2 * 0.85**2))
    finder = IRAFStarFinder(threshold=5.0, fwhm=2.0, exclude_border=True)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        result = finder.find_stars(data)
    assert result is None
