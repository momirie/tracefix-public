import pandas as pd
from shapely.geometry import Point
from geopandas import GeoDataFrame
from movingpandas import Trajectory


def _make_traj():
    idx = pd.to_datetime([
        "2024-10-25 07:39:31.250000477",
        "2024-10-25 07:39:32.250000477",
        "2024-10-25 07:39:33.250000477",
    ])
    df = pd.DataFrame({"geometry": [Point(0, 0), Point(1, 0), Point(3, 0)]}, index=idx)
    gdf = GeoDataFrame(df, crs="EPSG:31256")
    return Trajectory(gdf, 1)


def test_add_distance_nanosecond_no_extra_row():
    traj = _make_traj()
    traj.add_distance()
    assert len(traj.df) == 3
    assert traj.df["distance"].notna().all()
    assert traj.df["distance"].iloc[0] == 0
