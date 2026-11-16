import pandas as pd
from shapely.geometry import Point
from geopandas import GeoDataFrame
from pyproj import CRS

from movingpandas.trajectory import Trajectory


def _make_traj():
    times = [
        pd.Timestamp("2024-10-25 07:39:31.250000477"),
        pd.Timestamp("2024-10-25 07:39:32.250000477"),
        pd.Timestamp("2024-10-25 07:39:33.250000477"),
    ]
    df = pd.DataFrame(
        {"geometry": [Point(0, 0), Point(1, 0), Point(3, 0)], "t": times}
    ).set_index("t")
    gdf = GeoDataFrame(df, crs=CRS(31256))
    return Trajectory(gdf, 1)


def test_add_distance_nanosecond_index():
    traj = _make_traj()
    traj.add_distance()
    assert len(traj.df) == 3
    assert traj.df["distance"].iloc[0] == 0


def test_add_acceleration_nanosecond_index():
    traj = _make_traj()
    traj.add_acceleration()
    assert len(traj.df) == 3
