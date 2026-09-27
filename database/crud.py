"""
CRUD operations for database models.

Transaction-safe database operations for the DB-driven forecast system.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, asc
from sqlalchemy.dialects.postgresql import insert
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from uuid import UUID
import uuid

from database.models import (
    User,
    Hospital,
    AdmissionHistory,
    ForecastRun,
    Forecast,
    ExternalSignal,
)


# ============================================================================
# Hospital CRUD
# ============================================================================


def get_hospital_by_id(db: Session, hospital_id: str) -> Optional[Hospital]:
    """Get hospital by hospital_id string."""
    return db.query(Hospital).filter(Hospital.hospital_id == hospital_id).first()


def get_or_create_hospital(db: Session, hospital_id: str, **kwargs) -> Hospital:
    """Get existing hospital or create new one."""
    hospital = get_hospital_by_id(db, hospital_id)
    if hospital:
        return hospital

    hospital = Hospital(
        hospital_id=hospital_id,
        name=kwargs.get("name"),
        region=kwargs.get("region"),
        capacity=kwargs.get("capacity"),
        population=kwargs.get("population", 0),
        population_density=kwargs.get("population_density", 0.0),
        elderly_ratio=kwargs.get("elderly_ratio", 0.0),
        icu_capacity=kwargs.get("icu_capacity", 0),
    )
    db.add(hospital)
    db.flush()
    return hospital


def get_all_hospitals(db: Session, skip: int = 0, limit: int = 100) -> List[Hospital]:
    """Get all hospitals with pagination."""
    return db.query(Hospital).offset(skip).limit(limit).all()


def get_hospital_count(db: Session) -> int:
    """Get total number of hospitals."""
    return db.query(func.count(Hospital.id)).scalar() or 0


def get_all_hospital_ids(db: Session) -> List[str]:
    """Get all hospital_id strings."""
    rows = db.query(Hospital.hospital_id).order_by(Hospital.hospital_id).all()
    return [r[0] for r in rows]


# ============================================================================
# ForecastRun CRUD
# ============================================================================


def create_forecast_run(
    db: Session,
    hospital_count: int,
    horizon_count: int,
    total_forecasts: int,
    inference_time_seconds: Optional[float] = None,
    model_version: Optional[str] = None,
    user_id: Optional[UUID] = None,
    signal_date_used: Optional[date] = None,
) -> ForecastRun:
    """Create a new forecast run record."""
    forecast_run = ForecastRun(
        user_id=user_id,
        hospital_count=hospital_count,
        horizon_count=horizon_count,
        total_forecasts=total_forecasts,
        inference_time_seconds=inference_time_seconds,
        model_version=model_version,
        signal_date_used=signal_date_used,
    )
    db.add(forecast_run)
    db.flush()
    return forecast_run


def get_forecast_run(db: Session, run_id: UUID) -> Optional[ForecastRun]:
    """Get forecast run by ID."""
    return db.query(ForecastRun).filter(ForecastRun.id == run_id).first()


def get_latest_forecast_run(db: Session) -> Optional[ForecastRun]:
    """Get the most recent forecast run."""
    return db.query(ForecastRun).order_by(desc(ForecastRun.created_at)).first()


# ============================================================================
# Forecast CRUD
# ============================================================================


def create_forecast(
    db: Session,
    forecast_run_id: UUID,
    hospital_id: UUID,
    horizon: int,
    prediction: float,
    forecast_date: date,
) -> Forecast:
    """Create a single forecast record."""
    forecast = Forecast(
        forecast_run_id=forecast_run_id,
        hospital_id=hospital_id,
        horizon=horizon,
        prediction=prediction,
        forecast_date=forecast_date,
    )
    db.add(forecast)
    return forecast


def create_forecasts_batch(
    db: Session, forecast_run_id: UUID, forecasts_data: List[Dict[str, Any]]
) -> None:
    """
    Create multiple forecast records using UPSERT.
    Idempotent: ON CONFLICT (hospital_id, forecast_date, horizon) DO UPDATE.
    """
    if not forecasts_data:
        return

    # Resolve hospital string IDs to UUID FKs
    hospital_id_values = sorted({data["hospital_id"] for data in forecasts_data})
    existing_hospitals = (
        db.query(Hospital)
        .filter(Hospital.hospital_id.in_(hospital_id_values))
        .all()
    )
    hospital_map: Dict[str, Hospital] = {
        hospital.hospital_id: hospital for hospital in existing_hospitals
    }

    for hospital_id in hospital_id_values:
        if hospital_id not in hospital_map:
            hospital_map[hospital_id] = get_or_create_hospital(db, hospital_id)

    db.flush()

    created_at = datetime.utcnow()
    forecast_rows: List[Dict[str, Any]] = []
    for data in forecasts_data:
        forecast_rows.append(
            {
                "id": uuid.uuid4(),
                "forecast_run_id": forecast_run_id,
                "hospital_id": hospital_map[data["hospital_id"]].id,
                "target": data.get("target", "admissions"),
                "horizon": data["horizon"],
                "prediction": data["prediction"],
                "prediction_low": data.get("prediction_low"),
                "prediction_high": data.get("prediction_high"),
                "resource_gap": data.get("resource_gap"),
                "capacity_source": data.get("capacity_source"),
                "forecast_date": data["forecast_date"],
                "created_at": created_at,
            }
        )

    insert_stmt = insert(Forecast).values(forecast_rows)
    on_conflict_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["hospital_id", "forecast_date", "horizon", "target"],
        set_={
            "prediction": insert_stmt.excluded.prediction,
            "prediction_low": insert_stmt.excluded.prediction_low,
            "prediction_high": insert_stmt.excluded.prediction_high,
            "resource_gap": insert_stmt.excluded.resource_gap,
            "capacity_source": insert_stmt.excluded.capacity_source,
            "forecast_run_id": insert_stmt.excluded.forecast_run_id,
            "created_at": insert_stmt.excluded.created_at,
        },
    )
    db.execute(on_conflict_stmt)


def get_precomputed_forecasts(
    db: Session,
    run_id: UUID,
    hospital_ids: Optional[List[str]] = None,
    horizons: Optional[List[int]] = None,
    target: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get forecasts from a specific run, optionally filtered by hospital/horizon/target.
    Returns list of dicts ready for JSON serialization.
    """
    query = (
        db.query(Forecast, Hospital.hospital_id)
        .join(Hospital, Forecast.hospital_id == Hospital.id)
        .filter(Forecast.forecast_run_id == run_id)
    )

    if hospital_ids:
        query = query.filter(Hospital.hospital_id.in_(hospital_ids))

    if horizons:
        query = query.filter(Forecast.horizon.in_(horizons))

    if target:
        query = query.filter(Forecast.target == target)

    query = query.order_by(Hospital.hospital_id, Forecast.target, Forecast.horizon)

    results = []
    for forecast, hosp_id in query.all():
        results.append(
            {
                "hospital_id": hosp_id,
                "target": forecast.target,
                "horizon": forecast.horizon,
                "prediction": float(forecast.prediction),
                "prediction_low": float(forecast.prediction_low) if forecast.prediction_low is not None else None,
                "prediction_high": float(forecast.prediction_high) if forecast.prediction_high is not None else None,
                "resource_gap": float(forecast.resource_gap) if forecast.resource_gap is not None else None,
                "capacity_source": forecast.capacity_source,
                "forecast_date": str(forecast.forecast_date),
            }
        )
    return results


def get_forecasts(
    db: Session,
    hospital_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    horizon: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Forecast]:
    """Query forecasts with filtering and pagination."""
    query = db.query(Forecast)

    if hospital_id:
        hospital = get_hospital_by_id(db, hospital_id)
        if hospital:
            query = query.filter(Forecast.hospital_id == hospital.id)
        else:
            return []

    if start_date:
        query = query.filter(Forecast.forecast_date >= start_date)
    if end_date:
        query = query.filter(Forecast.forecast_date <= end_date)

    if horizon is not None:
        query = query.filter(Forecast.horizon == horizon)

    return query.order_by(desc(Forecast.forecast_date)).offset(skip).limit(limit).all()


def get_forecast_count(
    db: Session,
    hospital_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    horizon: Optional[int] = None,
) -> int:
    """Get total count of forecasts matching filters."""
    query = db.query(func.count(Forecast.id))

    if hospital_id:
        hospital = get_hospital_by_id(db, hospital_id)
        if hospital:
            query = query.filter(Forecast.hospital_id == hospital.id)
        else:
            return 0

    if start_date:
        query = query.filter(Forecast.forecast_date >= start_date)
    if end_date:
        query = query.filter(Forecast.forecast_date <= end_date)

    if horizon is not None:
        query = query.filter(Forecast.horizon == horizon)

    return query.scalar() or 0


# ============================================================================
# AdmissionHistory CRUD
# ============================================================================


def create_admission_history(
    db: Session, hospital_id: UUID, record_date: date, admissions: int
) -> AdmissionHistory:
    """Create admission history record."""
    admission = AdmissionHistory(
        hospital_id=hospital_id, date=record_date, admissions=admissions
    )
    db.add(admission)
    return admission


def upsert_admission_history_batch(
    db: Session, records: List[Dict[str, Any]]
) -> int:
    """
    Bulk UPSERT admission history. Idempotent.
    Each record: { hospital_uuid: UUID, date: date, admissions: int }
    """
    if not records:
        return 0

    rows = [
        {
            "id": uuid.uuid4(),
            "hospital_id": r["hospital_uuid"],
            "date": r["date"],
            "admissions": r["admissions"],
            "created_at": datetime.utcnow(),
        }
        for r in records
    ]

    insert_stmt = insert(AdmissionHistory).values(rows)
    upsert = insert_stmt.on_conflict_do_update(
        index_elements=["hospital_id", "date"],
        set_={"admissions": insert_stmt.excluded.admissions},
    )
    result = db.execute(upsert)
    return int(result.rowcount or 0)


def get_admission_history_for_hospitals(
    db: Session,
    hospital_ids: Optional[List[str]] = None,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Get admission history for hospitals, last N days relative to latest data."""
    from sqlalchemy import func as sa_func

    # Use latest date in DB (not today) so it works with historical data too
    max_date = db.query(sa_func.max(AdmissionHistory.date)).scalar()
    if max_date is None:
        return []
    cutoff = max_date - timedelta(days=days)

    query = (
        db.query(AdmissionHistory, Hospital.hospital_id)
        .join(Hospital, AdmissionHistory.hospital_id == Hospital.id)
        .filter(AdmissionHistory.date >= cutoff)
    )

    if hospital_ids:
        query = query.filter(Hospital.hospital_id.in_(hospital_ids))

    query = query.order_by(Hospital.hospital_id, AdmissionHistory.date)

    results = []
    for admission, hosp_id in query.all():
        results.append(
            {
                "hospital_id": hosp_id,
                "date": str(admission.date),
                "admissions": admission.admissions,
            }
        )
    return results


# ============================================================================
# ExternalSignal queries
# ============================================================================


def get_latest_signal_date(db: Session) -> Optional[date]:
    """Get the most recent external signal date across all hospitals."""
    result = db.query(func.max(ExternalSignal.date)).scalar()
    return result
