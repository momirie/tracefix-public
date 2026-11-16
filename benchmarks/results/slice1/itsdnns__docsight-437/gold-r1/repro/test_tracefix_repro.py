from app.modules.comparison.routes import _aggregate_period, _compute_delta


def _snap(ts, **summary):
    base = {"ds_power_avg": 1.0, "ds_snr_avg": 35.0, "us_power_avg": 40.0, "health": "good"}
    base.update(summary)
    return {"timestamp": ts, "summary": base}


def test_unsupported_errors_not_reported_as_zero():
    snaps = [_snap("2024-01-01T00:00:00Z", ds_correctable_errors=None, ds_uncorrectable_errors=None),
             _snap("2024-01-01T01:00:00Z", ds_correctable_errors=None, ds_uncorrectable_errors=None)]
    p = _aggregate_period(snaps)
    assert p["total"]["uncorr_errors"] is None
    assert p["total"]["corr_errors"] is None
    assert all(t["uncorr_errors"] is None for t in p["timeseries"])
    assert p["avg"]["ds_snr"] == 35.0
    d = _compute_delta(p, _aggregate_period(snaps))
    assert d["uncorr_errors"] is None


def test_missing_keys_not_zero():
    p = _aggregate_period([_snap("2024-01-01T00:00:00Z")])
    assert p["total"]["uncorr_errors"] is None
