from __future__ import annotations

import json
from datetime import date

from scripts.backfill_weather_features import backfill_weather, merge_cache_records, resolve_cooperative_coordinates
from app.models.cooperative import Cooperative
from app.models.enums import CooperativeStatus


def test_merge_cache_records_deduplicates_entries():
    existing = [
        {
            "cooperative_id": "c1",
            "latitude": 1.0,
            "longitude": 2.0,
            "timestamp": "2026-01-01T00:00:00Z",
            "source_kind": "observed_historical",
        }
    ]
    incoming = [
        {
            "cooperative_id": "c1",
            "latitude": 1.0,
            "longitude": 2.0,
            "timestamp": "2026-01-01T00:00:00Z",
            "source_kind": "observed_historical",
        }
    ]
    merged = merge_cache_records(existing, incoming)
    assert len(merged) == 1


def test_resolve_coordinates_uses_demo_fallback_when_present():
    coop = Cooperative(
        name="Demo Coop",
        region="Thies",
        address="Route test",
        phone="000",
        status=CooperativeStatus.ACTIVE,
    )
    coop.id = "demo-id"  # type: ignore[assignment]
    resolved = resolve_cooperative_coordinates(coop, {"demo-id": {"lat": 14.7, "lon": -16.9}})
    assert resolved is not None
    assert resolved.source.startswith("configured_demo_coordinates")


def test_dry_run_does_not_write_data(db_session, tmp_path, monkeypatch):
    from scripts import backfill_weather_features as mod

    cache = tmp_path / "weather.jsonl"
    monkeypatch.setattr(
        mod,
        "fetch_process_records",
        lambda db: [{"cooperative_id": "c1", "date": date(2026, 1, 1)}],
    )

    class DummyCoop:
        id = "c1"
        name = "C1"
        region = "Thies"
        address = "addr"

    monkeypatch.setattr(
        db_session,
        "scalars",
        lambda stmt: type("R", (), {"all": lambda self: [DummyCoop()]})(),
    )
    monkeypatch.setattr(
        mod,
        "resolve_cooperative_coordinates",
        lambda coop, demo_coords: mod.CoordinateResolution(latitude=14.7, longitude=-16.9, source="configured_demo_coordinates:test"),
    )
    monkeypatch.setattr(
        mod,
        "fetch_open_meteo_hourly",
        lambda **kwargs: [{"timestamp": "2026-01-01T00:00:00Z", "temperature": 30, "relative_humidity": 70, "dew_point": 20, "precipitation": 0, "wind_speed": 3, "surface_pressure": 1010}],
    )

    summary = backfill_weather(db_session, dry_run=True, start_date=None, end_date=None, cache_file=cache, chunk_days=31)
    assert summary["dry_run"] is True
    assert summary["cache_written"] is False
    assert not cache.exists()


def test_missing_coordinates_warns(db_session, tmp_path, monkeypatch):
    from scripts import backfill_weather_features as mod

    cache = tmp_path / "weather.jsonl"
    monkeypatch.setattr(
        mod,
        "fetch_process_records",
        lambda db: [{"cooperative_id": "c1", "date": date(2026, 1, 1)}],
    )

    class DummyCoop:
        id = "c1"
        name = "C1"
        region = "X"
        address = "Y"

    monkeypatch.setattr(
        db_session,
        "scalars",
        lambda stmt: type("R", (), {"all": lambda self: [DummyCoop()]})(),
    )
    monkeypatch.setattr(mod, "resolve_cooperative_coordinates", lambda coop, demo_coords: None)

    summary = backfill_weather(db_session, dry_run=True, start_date=None, end_date=None, cache_file=cache, chunk_days=31)
    assert any(str(item).startswith("MISSING_COORDINATES") for item in summary["warnings"])


def test_weather_coverage_increases_when_cache_exists(db_session, tmp_path, monkeypatch):
    from app.ml.features.engineer import build_features

    cache = tmp_path / "weather.jsonl"
    rows = [
        {
            "cooperative_id": "c1",
            "latitude": 14.7,
            "longitude": -16.9,
            "timestamp": "2026-01-01T00:00:00Z",
            "temperature": 30.0,
            "relative_humidity": 71.0,
            "dew_point": 21.0,
            "precipitation": 0.0,
            "wind_speed": 3.0,
            "surface_pressure": 1010.0,
            "source_kind": "observed_historical",
        }
    ]
    cache.write_text("\n".join(json.dumps(item) for item in rows) + "\n")
    monkeypatch.setenv("WEEFARM_WEATHER_CACHE_PATH", str(cache))

    # Keep this deterministic by overriding ML fetch records to align date and coop id.
    from app.ml import features as features_pkg
    monkeypatch.setattr(
        features_pkg.engineer,
        "fetch_process_records",
        lambda db: [
            {
                "batch_id": "b1",
                "cooperative_id": "c1",
                "product": "Mangue",
                "process_type": "Sechage",
                "qty_in": 100.0,
                "qty_out": 90.0,
                "batch_size": 100.0,
                "batch_current_qty": 90.0,
                "date": date(2026, 1, 1),
                "stock_level": 50.0,
            }
        ],
    )

    feature_set = build_features(db_session, include_weather=True)
    assert feature_set.diagnostics is not None
    weather_diag = feature_set.diagnostics["weather"]
    assert weather_diag["coverage_rate"] > 0.0
