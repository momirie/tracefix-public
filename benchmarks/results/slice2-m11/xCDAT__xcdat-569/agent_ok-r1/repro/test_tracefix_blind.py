import numpy as np
import xarray as xr

import xcdat  # noqa: F401


def test_add_missing_bounds_default_axes():
    ds = xr.Dataset(
        coords={
            "lat": xr.DataArray(
                np.array([-45.0, 0.0, 45.0]),
                dims="lat",
                attrs={"axis": "Y", "units": "degrees_north"},
            ),
            "lon": xr.DataArray(
                np.array([0.0, 90.0, 180.0, 270.0]),
                dims="lon",
                attrs={"axis": "X", "units": "degrees_east"},
            ),
        }
    )
    result = ds.bounds.add_missing_bounds()
    assert "lat_bnds" in result
    assert "lon_bnds" in result
