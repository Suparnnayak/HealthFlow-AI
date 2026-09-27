"""
External data ingestion service using free, no-key APIs.
"""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import logging
from typing import Dict, List, Tuple
import uuid

import requests as _requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from database.models import ExternalSignal, Hospital

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Stable default center (used with deterministic offsets per hospital_id)
DEFAULT_LATITUDE = 28.6139
DEFAULT_LONGITUDE = 77.2090


def _deterministic_coordinates(hospital_id: str) -> Tuple[float, float]:
    """
    Generate deterministic pseudo coordinates per hospital_id.
    Keeps API calls stable without requiring extra schema columns.
    """
    digest = hashlib.sha256(hospital_id.encode("utf-8")).hexdigest()
    lat_offset = ((int(digest[:8], 16) % 1200) - 600) / 1000.0
    lon_offset = ((int(digest[8:16], 16) % 1200) - 600) / 1000.0
    return DEFAULT_LATITUDE + lat_offset, DEFAULT_LONGITUDE + lon_offset


def fetch_weather(latitude: float, longitude: float) -> Dict[str, float]:
    """
    Fetch current weather from Open-Meteo forecast API.
    """
    response = _requests.get(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "UTC",
            "forecast_days": 1,
        },
        timeout=5,  # tight per-request timeout; caller catches exceptions
    )
    response.raise_for_status()
    payload = response.json()

    current_temp = float(payload.get("current", {}).get("temperature_2m", 0.0))
    daily = payload.get("daily", {}) or {}
    temp_max_list = daily.get("temperature_2m_max", []) or [current_temp]
    temp_min_list = daily.get("temperature_2m_min", []) or [current_temp]
    temp_max = float(temp_max_list[0])
    temp_min = float(temp_min_list[0])
    temp_variation = temp_max - temp_min

    return {
        "temperature": current_temp,
        "temp_variation": float(temp_variation),
    }


def fetch_aqi(latitude: float, longitude: float) -> float:
    """
    Fetch current AQI from Open-Meteo air quality API.
    """
    response = _requests.get(
        OPEN_METEO_AIR_QUALITY_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "us_aqi",
            "timezone": "UTC",
            "forecast_days": 1,
        },
        timeout=5,  # tight per-request timeout; caller catches exceptions
    )
    response.raise_for_status()
    payload = response.json()
    return float(payload.get("current", {}).get("us_aqi", 0.0))


def compute_outbreak_index(aqi: float, temp_variation: float) -> float:
    """
    Compute a normalized outbreak proxy index in [0, 1].
    """
    aqi_norm = min(max(aqi / 300.0, 0.0), 1.0)
    variation_norm = min(max(abs(temp_variation) / 20.0, 0.0), 1.0)
    return round(min(max((0.8 * aqi_norm) + (0.2 * variation_norm), 0.0), 1.0), 4)


def compute_mobility_index(day_of_week: int, is_weekend: bool) -> float:
    """
    Deterministic mobility proxy based on weekday/weekend profile.
    """
    base = 0.55 if is_weekend else 0.75
    weekday_shape = (3 - abs(3 - day_of_week)) * 0.01  # Mid-week slightly higher
    return round(min(max(base + weekday_shape, 0.0), 1.0), 4)


def get_latest_external_signals_by_hospital(
    db: Session, hospital_ids: List[str]
) -> Dict[str, Dict[str, float]]:
    """
    Return latest signal values keyed by hospital_id (string).
    """
    if not hospital_ids:
        return {}

    rows = (
        db.query(Hospital.hospital_id, ExternalSignal)
        .join(ExternalSignal, ExternalSignal.hospital_id == Hospital.id)
        .filter(Hospital.hospital_id.in_(hospital_ids))
        .order_by(Hospital.hospital_id.asc(), ExternalSignal.date.desc(), ExternalSignal.created_at.desc())
        .all()
    )

    latest: Dict[str, Dict[str, float]] = {}
    for hospital_id, signal in rows:
        if hospital_id in latest:
            continue
        latest[hospital_id] = {
            "temperature": float(signal.temperature),
            "aqi": float(signal.aqi),
            "outbreak_index": float(signal.outbreak_index),
            "mobility_index": float(signal.mobility_index),
        }
    return latest


def fetch_and_store_external_signals(db: Session) -> Dict[str, int]:
    """
    Fetch today's weather/AQI for all hospitals and upsert into external_signals.
    """
    hospitals = db.query(Hospital).all()
    today = date.today()
    created_at = datetime.utcnow()

    rows_to_upsert: List[Dict] = []
    failed = 0

    day_of_week = today.weekday()
    is_weekend = day_of_week >= 5

    for hospital in hospitals:
        try:
            latitude, longitude = _deterministic_coordinates(hospital.hospital_id)
            weather = fetch_weather(latitude, longitude)
            aqi = fetch_aqi(latitude, longitude)
            outbreak_index = compute_outbreak_index(
                aqi=aqi, temp_variation=weather["temp_variation"]
            )
            mobility_index = compute_mobility_index(
                day_of_week=day_of_week, is_weekend=is_weekend
            )

            rows_to_upsert.append(
                {
                    "id": uuid.uuid4(),
                    "hospital_id": hospital.id,
                    "date": today,
                    "temperature": weather["temperature"],
                    "aqi": aqi,
                    "outbreak_index": outbreak_index,
                    "mobility_index": mobility_index,
                    "created_at": created_at,
                }
            )
        except Exception:
            failed += 1

    if not rows_to_upsert:
        return {
            "hospitals_total": len(hospitals),
            "processed": 0,
            "failed": failed,
            "upserted": 0,
        }

    insert_stmt = insert(ExternalSignal).values(rows_to_upsert)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["hospital_id", "date"],
        set_={
            "temperature": insert_stmt.excluded.temperature,
            "aqi": insert_stmt.excluded.aqi,
            "outbreak_index": insert_stmt.excluded.outbreak_index,
            "mobility_index": insert_stmt.excluded.mobility_index,
            "created_at": insert_stmt.excluded.created_at,
        },
    )

    try:
        result = db.execute(upsert_stmt)
        db.commit()
        upserted = int(result.rowcount or 0)
    except Exception:
        db.rollback()
        raise

    return {
        "hospitals_total": len(hospitals),
        "processed": len(rows_to_upsert),
        "failed": failed,
        "upserted": upserted,
    }

