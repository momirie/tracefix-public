import pandas as pd
from shapely.geometry import Point
from geopandas import GeoDataFrame
from movingpandas.trajectory import Trajectory


def _make_traj():
    t0 = pd.Timestamp("2024-10-25 07:39:31.250000477")
    times = [t0 + pd.Timedelta(seconds=i) for i in range(4)]
    df = pd.DataFrame(
        {"geometry": [Point(i, 0) for i in range(4)], "t": times}
    ).set_index("t")
    gdf = GeoDataFrame(df, crs="EPSG:31256")
    return Trajectory(gdf, 1)


def test_add_speed_nanosecond_index_no_extra_row():
    traj = _make_traj()
    traj.add_speed()
    assert len(traj.df) == 4
    assert not traj.df["speed"].isna().any()


def test_add_distance_nanosecond_index_no_extra_row():
    traj = _make_traj()
    traj.add_distance()
    assert len(traj.df) == 4
    assert not traj.df["distance"].isna().any()
