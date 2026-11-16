import numpy as np
import xarray as xr

import xcdat  # noqa: F401


def _make_ds():
    lat = xr.DataArray(np.array([-45.0, 0.0, 45.0]), dims="lat", attrs={"axis": "Y", "units": "degrees_north", "standard_name": "latitude"})
    lon = xr.DataArray(np.array([0.0, 90.0, 180.0, 270.0]), dims="lon", attrs={"axis": "X", "units": "degrees_east", "standard_name": "longitude"})
    data = xr.DataArray(np.ones((3, 4)), dims=["lat", "lon"], coords={"lat": lat, "lon": lon}, name="ts")
    return data.to_dataset()


def test_add_missing_bounds_no_args():
    ds = _make_ds()
    result = ds.bounds.add_missing_bounds()
    assert "lat_bnds" in result
    assert "lon_bnds" in result


def test_add_missing_bounds_single_string_axis():
    ds = _make_ds()
    result = ds.bounds.add_missing_bounds("X")
    assert "lon_bnds" in result
    assert "lat_bnds" not in result
