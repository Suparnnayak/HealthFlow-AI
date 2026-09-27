"""
Hospital Forecast API — DB-Driven Architecture

Production FastAPI application.
- NO CSV dependency
- Forecasts are precomputed by daily_forecast_job.py
- All data lives in PostgreSQL (Neon)
- Read-only forecast endpoints
- Vercel-serverless compatible (no file writes in requests,
  no background schedulers, stateless handlers)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any
import os
import time
import threading
import uuid as _uuid
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import defaultdict
import subprocess
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text

# ---------- lightweight internal imports (no ML libraries) ----------
from forecast_system.utils import get_logger
from database.session import get_db
import database.crud as crud
from database.models import (
    User,
    Hospital,
    Forecast,
    ForecastRun,
    AdmissionHistory,
    ExternalSignal,
    AccessLog,
    UserHospitalAccess,
)
from app.auth.router import router as auth_router
from app.agent.router import router as agent_router
from app.dependencies import get_current_user, require_admin, require_hospital_access
from app.core.access_logger import log_access
from app.services.external_data_service import (
    fetch_and_store_external_signals,
    get_latest_external_signals_by_hospital,
)

# NOTE: ModelBundleV2 is imported lazily inside _load_model_bundle() so that
# the heavy ML stack is not required for cold serverless starts.

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level state — initialised once per cold start (Vercel or local)
# ---------------------------------------------------------------------------
MODEL_PATH = os.getenv(
    "MODEL_PATH", "models/forecast_system/model_bundle_v2.pkl"
)

bundle: Any = None                    # Optional[ModelBundleV2] when ML libs are present
model_loaded_at: Optional[str] = None
model_path_used: Optional[str] = None
model_version_str: str = "2.0.0"


def _load_model_bundle() -> None:
    """
    Load the model bundle from disk (called once at cold start).
    Tries ModelBundleV2 first, falling back to legacy ModelBundle if needed.
    """
    global bundle, model_loaded_at, model_path_used, model_version_str

    project_root = Path(__file__).resolve().parent.parent

    candidate_paths = [
        Path(MODEL_PATH),                     # explicit / absolute
        project_root / MODEL_PATH,            # relative to project root
        project_root / "models" / "forecast_system" / "model_bundle_v2.pkl",
        project_root / "models" / "forecast_system" / "lightgbm_final.pkl",
    ]

    for path in candidate_paths:
        path_str = str(path)
        if os.path.exists(path_str):
            # Try V2 bundle first
            try:
                from forecast_system.model_bundle_v2 import ModelBundleV2
                bundle = ModelBundleV2.load(path_str)
                model_path_used = path_str
                model_loaded_at = bundle.metadata.get("trained_at", datetime.now().isoformat())
                model_version_str = bundle.metadata.get("version", "2.0.0")
                logger.info(f"[OK] ModelBundleV2 loaded from: {path_str} (version {model_version_str})")
                return
            except Exception as e_v2:
                # Try V1 bundle fallback
                try:
                    from forecast_system.model_bundle import ModelBundle
                    bundle = ModelBundle.load(path_str)
                    model_path_used = path_str
                    model_loaded_at = datetime.now().isoformat()
                    model_version_str = "1.0.0"
                    logger.info(f"[OK] ModelBundle V1 loaded from: {path_str}")
                    return
                except Exception as e_v1:
                    logger.warning(f"[WARN] Failed loading {path_str}: V2 error ({e_v2}), V1 error ({e_v1})")

    logger.warning("[WARN] Model bundle not found — /model-info will be unavailable")


def _verify_db_connection() -> None:
    """
    Lightweight DB smoke-test at cold start.

    Does NOT call Base.metadata.create_all() — schema is managed
    exclusively by Alembic migrations.  This only opens one connection
    and runs ``SELECT 1`` to surface config errors early.
    """
    from database.session import SessionLocal

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("[OK] Database connection verified")
    except Exception as exc:
        logger.warning(f"[WARN] Database connection failed: {exc}")


# Run once at module-import time so both local uvicorn and Vercel
# cold-starts get the same behavior without relying on ASGI lifespan.
_verify_db_connection()
_load_model_bundle()


# ---------------------------------------------------------------------------
# ASGI lifespan (kept for local uvicorn; Vercel handles cold-start separately)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):
    # startup — already done at module level, nothing extra needed
    yield
    # shutdown — nothing to clean up


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001",
).split(",")

app = FastAPI(
    title="Hospital Forecast API",
    description="7-day hospital admissions forecasting system — DB-driven architecture",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — origins driven by ALLOWED_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Include authentication routes
app.include_router(auth_router)

# Include agent routes
app.include_router(agent_router, prefix="/agent", tags=["Agent"])

# Rate limiting (simple in-memory — resets on each cold start; fine for serverless)
rate_limit_store: defaultdict = defaultdict(list)
RATE_LIMIT_REQUESTS = 50
RATE_LIMIT_WINDOW = 60  # seconds


# ============================================================================
# UTILITY
# ============================================================================


def check_rate_limit(request: Request):
    """Simple rate limiting middleware."""
    client_ip = request.client.host
    now = time.time()
    rate_limit_store[client_ip] = [
        ts for ts in rate_limit_store[client_ip] if now - ts < RATE_LIMIT_WINDOW
    ]
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s",
        )
    rate_limit_store[client_ip].append(now)
    return True


def get_git_commit() -> Optional[str]:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


# ============================================================================
# SCHEMAS
# ============================================================================


class ForecastRequest(BaseModel):
    """Request model for /predict (backward-compatible)."""

    hospital_ids: Optional[List[str]] = Field(
        None, description="List of hospital IDs to forecast"
    )
    horizons: Optional[List[int]] = Field(
        [1, 2, 3, 4], description="Forecast horizons in weeks (1-4)"
    )
    target: Optional[str] = Field(
        None, description="Target: 'admissions' | 'inpatient_beds_used' (returns both if None)"
    )

    @validator("hospital_ids")
    def validate_hospital_ids(cls, v):
        if v is not None:
            if len(v) == 0:
                raise ValueError("hospital_ids cannot be empty list")
            if len(v) != len(set(v)):
                raise ValueError("hospital_ids contains duplicates")
        return v

    @validator("horizons")
    def validate_horizons(cls, v):
        if v is None or len(v) == 0:
            raise ValueError("horizons cannot be empty")
        if len(v) != len(set(v)):
            raise ValueError("horizons contains duplicates")
        for h in v:
            if h < 1:
                raise ValueError(f"horizon must be >= 1, got {h}")
            if h > 4:
                raise ValueError(f"horizon must be <= 4 weeks, got {h}")
        return sorted(v)


class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    status: str
    model_loaded: bool
    db_connected: bool


class ModelInfoResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    version: str = "1.0.0"
    trained_at: Optional[str] = None
    feature_count: int
    feature_columns: List[str]
    path: Optional[str] = None
    git_commit: Optional[str] = None


class SystemStatusResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_version: Optional[str] = None
    last_forecast_run: Optional[str] = None
    last_signal_update: Optional[str] = None
    hospitals_count: int = 0


class ExternalSignalsTaskResponse(BaseModel):
    status: str
    job_id: Optional[str] = None
    hospitals_total: int
    message: Optional[str] = None
    # synchronous-mode fields (kept for backward compat, None in async mode)
    processed: Optional[int] = None
    failed: Optional[int] = None
    upserted: Optional[int] = None


# ============================================================================
# BASIC ENDPOINTS
# ============================================================================


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "status": "Hospital Forecast API running",
        "version": "2.0.0",
        "architecture": "DB-driven, precomputed forecasts",
        "endpoints": {
            "/health": "Health check",
            "/hospitals": "List hospitals",
            "/forecast/latest": "Latest precomputed forecasts (GET)",
            "/forecast/history": "Admission history (GET)",
            "/system/status": "System status (GET)",
            "/predict": "Precomputed forecasts (POST, backward-compatible)",
            "/auth/register": "Register new user (POST)",
            "/auth/login": "Login and get JWT (POST)",
            "/agent/query": "AI-powered forecast explanation (POST, auth required)",
            "/docs": "API documentation",
        },
    }


@app.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        model_loaded=bundle is not None,
        db_connected=db_ok,
    )


# ============================================================================
# HOSPITALS (from DB, not CSV)
# ============================================================================


@app.get("/hospitals")
def list_hospitals(
    db: Session = Depends(get_db),
    user_claims: tuple = Depends(require_hospital_access),
):
    """
    List available hospitals.
    - Admins see all hospitals.
    - Staff see only their assigned hospital CCNs.
    Returns both 'hospitals' (list of IDs) for backward compatibility
    and 'items' with full metadata (name, region, capacity, etc.).
    """
    current_user, scoped_ids = user_claims
    if current_user.role == "admin":
        hosp_records = db.query(Hospital).order_by(Hospital.hospital_id).all()
    else:
        hosp_records = (
            db.query(Hospital)
            .filter(Hospital.hospital_id.in_(scoped_ids or []))
            .order_by(Hospital.hospital_id)
            .all()
        )

    items = [
        {
            "hospital_id": h.hospital_id,
            "name": h.name or f"Hospital {h.hospital_id}",
            "region": h.region or "Unknown",
            "capacity": h.capacity or 200,
            "icu_capacity": h.icu_capacity or 20,
        }
        for h in hosp_records
    ]
    hospital_ids = [h["hospital_id"] for h in items]

    return {
        "hospitals": hospital_ids,
        "items": items,
        "count": len(items),
    }


@app.get("/hospitals/public")
def list_public_hospitals(
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=2000),
):
    """
    Public lightweight endpoint returning available hospital IDs and details
    for registration dropdowns and facility selectors.
    """
    from database.models import Hospital
    rows = (
        db.query(Hospital.hospital_id, Hospital.name, Hospital.region, Hospital.capacity)
        .order_by(Hospital.hospital_id)
        .limit(limit)
        .all()
    )
    return {
        "hospitals": [
            {
                "hospital_id": r.hospital_id,
                "name": r.name or f"Hospital {r.hospital_id}",
                "region": r.region or "Unknown",
                "capacity": r.capacity or 200,
            }
            for r in rows
        ],
        "count": len(rows),
    }


class HospitalCreateRequest(BaseModel):
    hospital_id: str
    name: Optional[str] = None
    region: Optional[str] = None
    capacity: Optional[int] = 200
    icu_capacity: Optional[int] = 20
    population: Optional[int] = 50000


@app.post("/admin/hospitals", status_code=status.HTTP_201_CREATED)
def create_hospital(
    payload: HospitalCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Admin-only endpoint to add a new hospital into the database.
    """
    from database.models import Hospital

    existing = db.query(Hospital).filter(Hospital.hospital_id == payload.hospital_id.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hospital ID '{payload.hospital_id}' already exists",
        )

    new_hosp = Hospital(
        hospital_id=payload.hospital_id.strip(),
        name=payload.name.strip() if payload.name else f"Hospital {payload.hospital_id.strip()}",
        region=payload.region.strip() if payload.region else "General",
        capacity=payload.capacity if payload.capacity and payload.capacity > 0 else 200,
        icu_capacity=payload.icu_capacity if payload.icu_capacity and payload.icu_capacity >= 0 else 20,
        population=payload.population or 50000,
    )
    db.add(new_hosp)
    db.commit()
    db.refresh(new_hosp)

    return {
        "status": "created",
        "hospital": {
            "hospital_id": new_hosp.hospital_id,
            "name": new_hosp.name,
            "region": new_hosp.region,
            "capacity": new_hosp.capacity,
            "icu_capacity": new_hosp.icu_capacity,
        },
    }


# ============================================================================
# FORECAST ENDPOINTS (read-only, precomputed)
# ============================================================================


@app.get("/forecast/latest")
def forecast_latest(
    hospitals: Optional[str] = Query(
        None, description="Comma-separated hospital IDs"
    ),
    target: Optional[str] = Query(
        None, description="Filter target: 'admissions' | 'inpatient_beds_used'"
    ),
    db: Session = Depends(get_db),
    auth_data: tuple = Depends(require_hospital_access),
):
    """
    GET /forecast/latest — returns precomputed forecasts from the latest run.
    Hospital-scoped: hospital_staff can only view assigned hospitals.
    """
    current_user, allowed_hospital_ids = auth_data

    # Log access
    log_access(
        user_id=str(current_user.id),
        hospital_id=",".join(allowed_hospital_ids) if allowed_hospital_ids else "ALL",
        endpoint="/forecast/latest",
        query_params={"hospitals": hospitals, "target": target},
    )

    latest_run = crud.get_latest_forecast_run(db)
    if not latest_run:
        raise HTTPException(
            status_code=404,
            detail="No forecast runs found. Run weekly_forecast_job first.",
        )

    forecasts = crud.get_precomputed_forecasts(
        db=db,
        run_id=latest_run.id,
        hospital_ids=allowed_hospital_ids,
        target=target,
    )

    return {
        "run_id": str(latest_run.id),
        "model_version": latest_run.model_version,
        "created_at": latest_run.created_at.isoformat() if latest_run.created_at else None,
        "signal_date_used": str(latest_run.signal_date_used) if latest_run.signal_date_used else None,
        "forecasts": forecasts,
        "count": len(forecasts),
    }


@app.get("/forecast/history")
def forecast_history(
    hospitals: Optional[str] = Query(
        None, description="Comma-separated hospital IDs"
    ),
    days: int = Query(60, ge=1, le=730, description="Number of days/weeks of history"),
    db: Session = Depends(get_db),
    auth_data: tuple = Depends(require_hospital_access),
):
    """
    GET /forecast/history — returns admission history from the database.
    Hospital-scoped: hospital_staff can only view assigned hospitals.
    """
    current_user, allowed_hospital_ids = auth_data

    # Log access
    log_access(
        user_id=str(current_user.id),
        hospital_id=",".join(allowed_hospital_ids) if allowed_hospital_ids else "ALL",
        endpoint="/forecast/history",
        query_params={"hospitals": hospitals, "days": days},
    )

    history = crud.get_admission_history_for_hospitals(
        db=db, hospital_ids=allowed_hospital_ids, days=days
    )

    return {"history": history, "count": len(history), "days": days}


@app.get("/system/status", response_model=SystemStatusResponse)
def system_status(db: Session = Depends(get_db)):
    """
    GET /system/status — returns system health summary.
    """
    # Latest forecast run
    latest_run = crud.get_latest_forecast_run(db)
    last_run_str = None
    model_version = None
    if latest_run:
        last_run_str = latest_run.created_at.isoformat() if latest_run.created_at else None
        model_version = latest_run.model_version

    # Latest external signal date
    signal_date = crud.get_latest_signal_date(db)
    signal_str = str(signal_date) if signal_date else None

    # Hospital count
    hosp_count = crud.get_hospital_count(db)

    return SystemStatusResponse(
        model_version=model_version,
        last_forecast_run=last_run_str,
        last_signal_update=signal_str,
        hospitals_count=hosp_count,
    )


# ============================================================================
# /predict — BACKWARD-COMPATIBLE (returns precomputed data, no live inference)
# ============================================================================


@app.post("/predict")
def predict(
    request: ForecastRequest,
    rate_limit: bool = Depends(check_rate_limit),
    db: Session = Depends(get_db),
    auth_data: tuple = Depends(require_hospital_access),
):
    """
    POST /predict — Returns precomputed forecasts with hospital scoping.
    """
    start_time = time.time()
    current_user, allowed_hospital_ids = auth_data

    # Log access
    log_access(
        user_id=str(current_user.id),
        hospital_id=",".join(allowed_hospital_ids) if allowed_hospital_ids else "ALL",
        endpoint="/predict",
        query_params={"hospital_ids": request.hospital_ids, "horizons": request.horizons, "target": request.target},
    )

    # Get latest forecast run
    latest_run = crud.get_latest_forecast_run(db)
    if not latest_run:
        raise HTTPException(
            status_code=503,
            detail="No precomputed forecasts available. Waiting for forecast job.",
        )

    available_hospitals = set(crud.get_all_hospital_ids(db))
    if not available_hospitals:
        raise HTTPException(status_code=503, detail="No hospitals in database")

    # If staff, ensure requested hospitals are subset of allowed
    if request.hospital_ids:
        if current_user.role != "admin":
            unauthorized = set(request.hospital_ids) - set(allowed_hospital_ids)
            if unauthorized:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to hospitals: {sorted(unauthorized)}",
                )
        requested_hospital_ids = request.hospital_ids
    else:
        requested_hospital_ids = allowed_hospital_ids if current_user.role != "admin" else sorted(available_hospitals)

    horizons = sorted(request.horizons) if request.horizons else [1, 2, 3, 4]

    # Fetch precomputed forecasts
    forecasts = crud.get_precomputed_forecasts(
        db=db,
        run_id=latest_run.id,
        hospital_ids=requested_hospital_ids,
        horizons=horizons,
        target=request.target,
    )

    elapsed = time.time() - start_time

    # Identify hospitals that returned zero forecast rows (admin-added, not in training set)
    hospitals_with_data = {f["hospital_id"] for f in forecasts}
    hospitals_without_forecasts = [h for h in requested_hospital_ids if h not in hospitals_with_data]

    if hospitals_without_forecasts:
        logger.warning(
            f"No forecast data found for hospitals: {hospitals_without_forecasts}. "
            "These hospitals may have been added after the last model training run."
        )

    logger.info(
        f"Predict (precomputed) | hospitals={len(requested_hospital_ids)} | "
        f"horizons={len(horizons)} | results={len(forecasts)} | time={elapsed:.3f}s"
    )

    return {
        "status": "success",
        "forecasts": forecasts,
        "count": len(forecasts),
        "metadata": {
            "hospitals_requested": len(requested_hospital_ids),
            "horizons_requested": len(horizons),
            "inference_time_seconds": round(elapsed, 3),
            "forecast_run_id": str(latest_run.id),
            "source": "precomputed",
            "hospitals_without_forecasts": hospitals_without_forecasts,
        },
    }


# ============================================================================
# MODEL INFO
# ============================================================================


@app.get(
    "/model-info",
    response_model=ModelInfoResponse,
    dependencies=[Depends(require_admin)],
)
def model_info():
    """Get model information (Admin-only)."""
    if bundle is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    feat_cols = getattr(bundle, "feature_columns", [])
    return ModelInfoResponse(
        version=model_version_str,
        trained_at=model_loaded_at,
        feature_count=len(feat_cols),
        feature_columns=feat_cols,
        path=model_path_used,
        git_commit=get_git_commit(),
    )


# ============================================================================
# ACCESS LOGS (ADMIN-ONLY)
# ============================================================================


@app.get("/admin/access-logs")
def get_access_logs(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    GET /admin/access-logs — returns audit access log records (Admin-only).
    """
    logs = (
        db.query(AccessLog, User.email)
        .outerjoin(User, AccessLog.user_id == User.id)
        .order_by(desc(AccessLog.timestamp))
        .limit(limit)
        .all()
    )

    results = []
    for log, email in logs:
        results.append(
            {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "user_email": email,
                "hospital_id": log.hospital_id,
                "endpoint": log.endpoint,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "query_params": log.query_params,
            }
        )

    return {"access_logs": results, "count": len(results)}


# ============================================================================
# STORED FORECASTS BROWSER (pagination)
# ============================================================================


class ForecastResponse(BaseModel):
    id: str
    hospital_id: str
    horizon: int
    prediction: float
    forecast_date: date
    created_at: datetime


class ForecastsListResponse(BaseModel):
    forecasts: List[ForecastResponse]
    total: int
    skip: int
    limit: int


@app.get("/forecasts", response_model=ForecastsListResponse)
def get_forecasts(
    hospital_id: Optional[str] = Query(None, description="Filter by hospital ID"),
    start_date: Optional[date] = Query(None, description="Filter >= start_date"),
    end_date: Optional[date] = Query(None, description="Filter <= end_date"),
    horizon: Optional[int] = Query(None, ge=1, le=7, description="Filter by horizon"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get stored forecasts with filtering and pagination."""
    try:
        forecasts = crud.get_forecasts(
            db=db,
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
            horizon=horizon,
            skip=skip,
            limit=limit,
        )

        total = crud.get_forecast_count(
            db=db,
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
            horizon=horizon,
        )

        forecast_responses = []
        for f in forecasts:
            hospital_id_str = f.hospital.hospital_id if f.hospital else "unknown"
            forecast_responses.append(
                ForecastResponse(
                    id=str(f.id),
                    hospital_id=hospital_id_str,
                    horizon=f.horizon,
                    prediction=f.prediction,
                    forecast_date=f.forecast_date,
                    created_at=f.created_at,
                )
            )

        return ForecastsListResponse(
            forecasts=forecast_responses, total=total, skip=skip, limit=limit
        )
    except Exception as e:
        logger.exception(f"Error retrieving forecasts: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving forecasts")


# ============================================================================
# EXTERNAL SIGNALS TASK
# ============================================================================


@app.post(
    "/tasks/fetch-external-signals",
    response_model=ExternalSignalsTaskResponse,
    status_code=202,
    dependencies=[Depends(require_admin)],
)
def run_fetch_external_signals_task(db: Session = Depends(get_db)):
    """
    Trigger an external-signal refresh for all hospitals (Admin-only).

    Returns 202 Accepted immediately. The actual work runs in a background
    daemon thread so uvicorn is not blocked. With 1,400+ hospitals and 2 API
    calls each, a synchronous run would exceed any reasonable HTTP timeout.

    The background thread uses its own DB session (not the request session)
    to avoid holding the connection across thread boundaries.
    """
    hospitals_total = db.query(Hospital).count()
    job_id = str(_uuid.uuid4())

    def _run_job() -> None:
        """Background worker — own DB session, own error handling."""
        from database.session import SessionLocal as _SessionLocal

        bg_db = _SessionLocal()
        try:
            summary = fetch_and_store_external_signals(bg_db)
            logger.info(
                f"[signals job {job_id}] complete: "
                f"processed={summary['processed']} "
                f"upserted={summary['upserted']} "
                f"failed={summary['failed']}"
            )
        except Exception as exc:
            logger.exception(f"[signals job {job_id}] failed: {exc}")
        finally:
            bg_db.close()

    thread = threading.Thread(target=_run_job, daemon=True, name=f"signals-{job_id[:8]}")
    thread.start()
    logger.info(f"[signals job {job_id}] dispatched background thread for {hospitals_total} hospitals")

    return ExternalSignalsTaskResponse(
        status="accepted",
        job_id=job_id,
        hospitals_total=hospitals_total,
        message=(
            f"Signal refresh for {hospitals_total} hospitals started in background. "
            f"Check server logs for job {job_id[:8]} to track progress."
        ),
    )
