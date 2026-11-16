import warnings

import numpy as np
from photutils.detection import IRAFStarFinder


def test_iraf_exclude_border_only_border_sources():
    yy, xx = np.mgrid[0:30, 0:30]
    data = 100.0 * np.exp(-((xx - 1) ** 2 + (yy - 1) ** 2) / (2 * 1.0 ** 2))
    finder = IRAFStarFinder(threshold=5.0, fwhm=2.0, exclude_border=True)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        result = finder.find_stars(data)
    assert result is None or len(result) == 0
