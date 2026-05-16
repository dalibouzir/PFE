#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ml.features.engineer import fetch_process_records
from app.ml.weather_features import fetch_open_meteo_hourly, load_cached_weather_records
from app.models.cooperative import Cooperative


@dataclass
class CoordinateResolution:
    latitude: float
    longitude: float
    source: str


def _cache_path(path: Optional[str]) -> Path:
    if path:
        return Path(path).expanduser()
    env_path = os.getenv("WEEFARM_WEATHER_CACHE_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return Path("backend/artifacts/weather_cache.jsonl")


def _load_demo_coords() -> Dict[str, Dict[str, float]]:
    file_path = Path("backend/artifacts/demo_cooperative_coords.json")
    payload: Dict[str, Dict[str, float]] = {}
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text())
            if isinstance(data, dict):
                payload.update(data)
        except Exception:
            pass
    env_json = os.getenv("WEEFARM_DEMO_COORDS_JSON", "").strip()
    if env_json:
        try:
            data = json.loads(env_json)
            if isinstance(data, dict):
                payload.update(data)
        except Exception:
            pass
    return payload


def _geocode_location(query: str) -> Optional[Tuple[float, float]]:
    if not query or httpx is None:
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query, "count": 1, "language": "en", "format": "json"},
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        return None
    results = data.get("results") or []
    if not results:
        return None
    first = results[0]
    lat = first.get("latitude")
    lon = first.get("longitude")
    try:
        return float(lat), float(lon)
    except Exception:
        return None


def resolve_cooperative_coordinates(coop: Cooperative, demo_coords: Dict[str, Dict[str, float]]) -> Optional[CoordinateResolution]:
    coop_id = str(coop.id)
    by_id = demo_coords.get(coop_id) if isinstance(demo_coords, dict) else None
    if isinstance(by_id, dict) and "lat" in by_id and "lon" in by_id:
        return CoordinateResolution(latitude=float(by_id["lat"]), longitude=float(by_id["lon"]), source="configured_demo_coordinates:id")

    by_name = demo_coords.get(coop.name) if isinstance(demo_coords, dict) else None
    if isinstance(by_name, dict) and "lat" in by_name and "lon" in by_name:
        return CoordinateResolution(latitude=float(by_name["lat"]), longitude=float(by_name["lon"]), source="configured_demo_coordinates:name")

    for text in (f"{coop.address}, {coop.region}", coop.address, coop.region, coop.name):
        point = _geocode_location(text)
        if point:
            return CoordinateResolution(latitude=point[0], longitude=point[1], source=f"geocoded:{text}")
    return None


def merge_cache_records(existing: Iterable[Dict], incoming: Iterable[Dict]) -> List[Dict]:
    merged: Dict[Tuple[str, str, str, str, str], Dict] = {}
    for item in list(existing) + list(incoming):
        coop_id = str(item.get("cooperative_id") or "")
        lat = str(item.get("latitude") or "")
        lon = str(item.get("longitude") or "")
        ts = str(item.get("timestamp") or "")
        source = str(item.get("source_kind") or "unknown")
        key = (coop_id, lat, lon, ts, source)
        merged[key] = item
    out = list(merged.values())
    out.sort(key=lambda row: (str(row.get("cooperative_id") or ""), str(row.get("timestamp") or "")))
    return out


def _date_chunks(start: date, end: date, chunk_days: int = 31) -> Iterable[Tuple[date, date]]:
    cursor = start
    while cursor <= end:
        right = min(end, cursor + timedelta(days=max(1, chunk_days) - 1))
        yield cursor, right
        cursor = right + timedelta(days=1)


def backfill_weather(
    db: Session,
    *,
    dry_run: bool,
    start_date: Optional[str],
    end_date: Optional[str],
    cache_file: Path,
    chunk_days: int = 31,
) -> Dict:
    process_rows = fetch_process_records(db)
    if not process_rows:
        return {"requested_rows": 0, "fetched_weather_records": 0, "cache_written": False, "warnings": ["NO_PROCESS_ROWS"]}

    events = []
    coop_ids = set()
    for row in process_rows:
        coop_id = row.get("cooperative_id")
        dt = row.get("date")
        if coop_id is None or dt is None:
            continue
        coop_ids.add(coop_id)
        events.append({"cooperative_id": str(coop_id), "event_date": dt})
    if not events:
        return {"requested_rows": len(process_rows), "fetched_weather_records": 0, "cache_written": False, "warnings": ["NO_EVENT_DATES"]}

    event_dates = [item["event_date"] for item in events]
    min_dt = min(event_dates)
    max_dt = max(event_dates)
    range_start = date.fromisoformat(start_date) if start_date else min_dt
    range_end = date.fromisoformat(end_date) if end_date else max_dt

    coop_rows = db.scalars(select(Cooperative).where(Cooperative.id.in_(list(coop_ids)))).all()
    coop_by_id = {str(c.id): c for c in coop_rows}
    demo_coords = _load_demo_coords()
    warnings: List[str] = []
    incoming_records: List[Dict] = []

    for coop_id in sorted({item["cooperative_id"] for item in events}):
        coop = coop_by_id.get(coop_id)
        if coop is None:
            warnings.append(f"MISSING_COOPERATIVE:{coop_id}")
            continue
        resolved = resolve_cooperative_coordinates(coop, demo_coords)
        if resolved is None:
            warnings.append(f"MISSING_COORDINATES:{coop_id}:{coop.name}")
            continue
        for left, right in _date_chunks(range_start, range_end, chunk_days=chunk_days):
            weather_rows = fetch_open_meteo_hourly(
                latitude=resolved.latitude,
                longitude=resolved.longitude,
                start_date=left.isoformat(),
                end_date=right.isoformat(),
            )
            for row in weather_rows:
                incoming_records.append(
                    {
                        "cooperative_id": coop_id,
                        "latitude": resolved.latitude,
                        "longitude": resolved.longitude,
                        "timestamp": row.get("timestamp"),
                        "temperature": row.get("temperature"),
                        "relative_humidity": row.get("relative_humidity"),
                        "dew_point": row.get("dew_point"),
                        "precipitation": row.get("precipitation"),
                        "wind_speed": row.get("wind_speed"),
                        "surface_pressure": row.get("surface_pressure"),
                        "source_kind": "observed_historical",
                        "coordinate_source": resolved.source,
                    }
                )

    existing = load_cached_weather_records(cache_file)
    merged = merge_cache_records(existing, incoming_records)
    cache_written = False
    if not dry_run:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(json.dumps(item, default=str) for item in merged)
        if payload:
            payload += "\n"
        cache_file.write_text(payload)
        cache_written = True

    unique_event_rows = len(events)
    with_coords = unique_event_rows if not any(w.startswith("MISSING_COORDINATES") for w in warnings) else 0
    return {
        "requested_rows": unique_event_rows,
        "cooperative_count": len({item["cooperative_id"] for item in events}),
        "date_range": {"start": range_start.isoformat(), "end": range_end.isoformat()},
        "fetched_weather_records": len(incoming_records),
        "existing_cache_records": len(existing),
        "merged_cache_records": len(merged),
        "cache_file": str(cache_file),
        "cache_written": cache_written,
        "dry_run": dry_run,
        "warnings": warnings,
        "coordinate_strategy": "geocoding_with_demo_fallback",
        "approx_event_coordinate_coverage": float(with_coords / unique_event_rows) if unique_event_rows else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical weather cache for ML weather features.")
    parser.add_argument("--dry-run", action="store_true", help="Compute and fetch without writing cache.")
    parser.add_argument("--start-date", default=None, help="Optional YYYY-MM-DD override.")
    parser.add_argument("--end-date", default=None, help="Optional YYYY-MM-DD override.")
    parser.add_argument("--cache-path", default=None, help="Optional cache file path.")
    parser.add_argument("--chunk-days", type=int, default=31, help="Chunk size for API pulls.")
    args = parser.parse_args()

    cache_file = _cache_path(args.cache_path)
    db = SessionLocal()
    try:
        summary = backfill_weather(
            db,
            dry_run=bool(args.dry_run),
            start_date=args.start_date,
            end_date=args.end_date,
            cache_file=cache_file,
            chunk_days=max(1, int(args.chunk_days)),
        )
    finally:
        db.close()

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
