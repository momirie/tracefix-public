import pandas as pd
from shapely.geometry import Point
from geopandas import GeoDataFrame
from movingpandas.trajectory import Trajectory


def _make_traj():
    times = pd.to_datetime([
        "2024-10-25 07:39:31.250000477",
        "2024-10-25 07:39:32.250000477",
        "2024-10-25 07:39:33.250000477",
    ])
    df = pd.DataFrame({"geometry": [Point(0, 0), Point(1, 1), Point(3, 3)]}, index=times)
    gdf = GeoDataFrame(df, crs="EPSG:31256")
    return Trajectory(gdf, 1), len(df)


def test_add_speed_nanosecond_index():
    traj, n = _make_traj()
    traj.add_speed()
    assert len(traj.df) == n
    assert not traj.df["speed"].isna().any()


def test_add_distance_nanosecond_index():
    traj, n = _make_traj()
    traj.add_distance()
    assert len(traj.df) == n
    assert not traj.df["distance"].isna().any()


def test_add_acceleration_nanosecond_index():
    traj, n = _make_traj()
    traj.add_acceleration()
    assert len(traj.df) == n
