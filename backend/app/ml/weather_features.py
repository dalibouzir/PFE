from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency at runtime
    httpx = None


UTC = timezone.utc


@dataclass
class WeatherFeaturesResult:
    frame: pd.DataFrame
    coverage: Dict[str, float]
    leakage_violations: int


def _safe_float(value: object) -> Optional[float]:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(out) or np.isinf(out):
        return None
    return out


def _to_utc_ts(value: object) -> Optional[pd.Timestamp]:
    try:
        ts = pd.to_datetime(value, utc=True)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts


def _default_weather_cache_path() -> Path:
    raw = os.getenv("WEEFARM_WEATHER_CACHE_PATH", "")
    if raw.strip():
        return Path(raw).expanduser()
    return Path("backend/artifacts/weather_cache.jsonl")


def load_cached_weather_records(path: Optional[Path] = None) -> List[Dict]:
    target = path or _default_weather_cache_path()
    if not target.exists():
        return []
    rows: List[Dict] = []
    try:
        for line in target.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            rows.append(payload)
    except Exception:
        return []
    return rows


def fetch_open_meteo_hourly(
    *,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    timeout_seconds: float = 20.0,
) -> List[Dict]:
    if httpx is None:
        return []
    base_url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "dew_point_2m",
                "precipitation",
                "wind_speed_10m",
                "surface_pressure",
            ]
        ),
        "timezone": "UTC",
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return []

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    out: List[Dict] = []
    for idx, item in enumerate(times):
        out.append(
            {
                "timestamp": item,
                "temperature": _safe_float((hourly.get("temperature_2m") or [None])[idx] if idx < len(hourly.get("temperature_2m") or []) else None),
                "relative_humidity": _safe_float((hourly.get("relative_humidity_2m") or [None])[idx] if idx < len(hourly.get("relative_humidity_2m") or []) else None),
                "dew_point": _safe_float((hourly.get("dew_point_2m") or [None])[idx] if idx < len(hourly.get("dew_point_2m") or []) else None),
                "precipitation": _safe_float((hourly.get("precipitation") or [None])[idx] if idx < len(hourly.get("precipitation") or []) else None),
                "wind_speed": _safe_float((hourly.get("wind_speed_10m") or [None])[idx] if idx < len(hourly.get("wind_speed_10m") or []) else None),
                "surface_pressure": _safe_float((hourly.get("surface_pressure") or [None])[idx] if idx < len(hourly.get("surface_pressure") or []) else None),
                "source_kind": "observed_historical",
            }
        )
    return out


def _records_to_frame(records: Iterable[Dict]) -> pd.DataFrame:
    rows = []
    for item in records:
        ts = _to_utc_ts(item.get("timestamp"))
        if ts is None:
            continue
        rows.append(
            {
                "weather_timestamp": ts,
                "temperature": _safe_float(item.get("temperature")),
                "relative_humidity": _safe_float(item.get("relative_humidity")),
                "dew_point": _safe_float(item.get("dew_point")),
                "precipitation": _safe_float(item.get("precipitation")),
                "wind_speed": _safe_float(item.get("wind_speed")),
                "surface_pressure": _safe_float(item.get("surface_pressure")),
                "source_kind": str(item.get("source_kind") or "unknown"),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "weather_timestamp",
                "temperature",
                "relative_humidity",
                "dew_point",
                "precipitation",
                "wind_speed",
                "surface_pressure",
                "source_kind",
            ]
        )
    frame = pd.DataFrame(rows).drop_duplicates(subset=["weather_timestamp"]).sort_values("weather_timestamp")
    return frame


def build_weather_feature_frame(
    events: pd.DataFrame,
    *,
    event_time_col: str = "date",
    cooperative_time_col: str = "cooperative_id",
    weather_records: Optional[List[Dict]] = None,
    window_hours: int = 24,
    enforce_leakage_check: bool = True,
) -> WeatherFeaturesResult:
    expected_cols = [
        "weather_available",
        "weather_feature_timestamp",
        "weather_avg_humidity_window",
        "weather_max_humidity_window",
        "weather_avg_temperature_window",
        "weather_avg_dew_point_window",
        "weather_avg_wind_speed_window",
        "weather_avg_surface_pressure_window",
        "weather_rain_flag_window",
        "weather_precip_total_window",
        "weather_source_kind",
        "weather_is_forecast",
        "weather_is_observed",
    ]
    if events.empty:
        return WeatherFeaturesResult(frame=pd.DataFrame(), coverage={"row_coverage_rate": 0.0}, leakage_violations=0)

    weather_rows = weather_records if weather_records is not None else load_cached_weather_records()
    weather_df = _records_to_frame(weather_rows)
    events_df = events.copy()
    events_df["_event_time"] = pd.to_datetime(events_df[event_time_col], utc=True, errors="coerce")
    window = timedelta(hours=max(1, int(window_hours)))

    result_rows: List[Dict] = []
    leakage_violations = 0

    for idx, row in events_df.iterrows():
        event_ts = row["_event_time"]
        if pd.isna(event_ts):
            result_rows.append({"_row_idx": idx, "weather_available": 0})
            continue

        if weather_df.empty:
            result_rows.append({"_row_idx": idx, "weather_available": 0})
            continue

        subset = weather_df[weather_df["weather_timestamp"] <= event_ts]
        subset = subset[subset["weather_timestamp"] >= (event_ts - window)]
        if subset.empty:
            future_window = weather_df[
                (weather_df["weather_timestamp"] > event_ts)
                & (weather_df["weather_timestamp"] <= (event_ts + window))
            ]
            if not future_window.empty:
                leakage_violations += 1
                if enforce_leakage_check:
                    raise ValueError(
                        "Weather leakage detected: only future weather rows are available within the feature window."
                    )
            result_rows.append({"_row_idx": idx, "weather_available": 0})
            continue

        max_ts = subset["weather_timestamp"].max()
        if max_ts > event_ts:
            leakage_violations += 1
            if enforce_leakage_check:
                raise ValueError(
                    f"Weather leakage detected: weather feature timestamp {max_ts} exceeds event time {event_ts}."
                )

        avg_humidity = subset["relative_humidity"].dropna().mean()
        max_humidity = subset["relative_humidity"].dropna().max()
        avg_temp = subset["temperature"].dropna().mean()
        avg_dew = subset["dew_point"].dropna().mean()
        avg_wind = subset["wind_speed"].dropna().mean()
        avg_pressure = subset["surface_pressure"].dropna().mean()
        rain_total = subset["precipitation"].dropna().sum()
        rain_flag = 1 if float(rain_total or 0.0) > 0.0 else 0
        latest_source_kind = str(subset.iloc[-1]["source_kind"] or "unknown")

        result_rows.append(
            {
                "_row_idx": idx,
                "weather_available": 1,
                "weather_feature_timestamp": max_ts,
                "weather_avg_humidity_window": float(avg_humidity) if pd.notna(avg_humidity) else None,
                "weather_max_humidity_window": float(max_humidity) if pd.notna(max_humidity) else None,
                "weather_avg_temperature_window": float(avg_temp) if pd.notna(avg_temp) else None,
                "weather_avg_dew_point_window": float(avg_dew) if pd.notna(avg_dew) else None,
                "weather_avg_wind_speed_window": float(avg_wind) if pd.notna(avg_wind) else None,
                "weather_avg_surface_pressure_window": float(avg_pressure) if pd.notna(avg_pressure) else None,
                "weather_rain_flag_window": rain_flag,
                "weather_precip_total_window": float(rain_total) if pd.notna(rain_total) else 0.0,
                "weather_source_kind": latest_source_kind,
                "weather_is_forecast": 1 if "forecast" in latest_source_kind else 0,
                "weather_is_observed": 1 if "observed" in latest_source_kind else 0,
            }
        )

    out = pd.DataFrame(result_rows).set_index("_row_idx")
    full = pd.DataFrame(index=events_df.index).join(out, how="left")
    full = full.reindex(columns=expected_cols)
    full["weather_available"] = pd.to_numeric(full["weather_available"], errors="coerce").fillna(0).astype(int)
    for col in [
        "weather_avg_humidity_window",
        "weather_max_humidity_window",
        "weather_avg_temperature_window",
        "weather_avg_dew_point_window",
        "weather_avg_wind_speed_window",
        "weather_avg_surface_pressure_window",
        "weather_precip_total_window",
    ]:
        full[col] = pd.to_numeric(full[col], errors="coerce")
    full["weather_rain_flag_window"] = pd.to_numeric(full.get("weather_rain_flag_window"), errors="coerce").fillna(0).astype(int)
    full["weather_is_forecast"] = pd.to_numeric(full.get("weather_is_forecast"), errors="coerce").fillna(0).astype(int)
    full["weather_is_observed"] = pd.to_numeric(full.get("weather_is_observed"), errors="coerce").fillna(0).astype(int)
    full["weather_source_kind"] = full.get("weather_source_kind", pd.Series(index=full.index, dtype=object)).fillna("missing")

    coverage = {
        "row_count": int(len(full)),
        "rows_with_weather": int(full["weather_available"].sum()),
        "rows_without_weather": int(len(full) - int(full["weather_available"].sum())),
        "row_coverage_rate": float(full["weather_available"].mean()) if len(full) else 0.0,
    }
    return WeatherFeaturesResult(frame=full.reset_index(drop=True), coverage=coverage, leakage_violations=leakage_violations)
