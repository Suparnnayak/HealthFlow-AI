"""
Agent service — DB context fetching + Groq LLM call.

This module is intentionally self-contained:
  • fetch_agent_context()  — pulls live data from PostgreSQL
  • build_prompt()         — assembles a grounded system+user message
  • call_groq()            — sends the prompt to the Groq Chat API
"""

from __future__ import annotations

import os
import re
import time
from datetime import date
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import httpx

# Ensure .env is loaded even if this module is imported before database.session
load_dotenv()
from fastapi import HTTPException, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from database.models import (
    AdmissionHistory,
    ExternalSignal,
    Forecast,
    ForecastRun,
    Hospital,
)
from forecast_system.utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Environment — read lazily so python-dotenv has time to load .env
# ---------------------------------------------------------------------------
GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
FALLBACK_MODELS: list[str] = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]


def _get_groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY", "")


def _get_groq_model() -> str:
    return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


# ---------------------------------------------------------------------------
# Hospital code extraction
# ---------------------------------------------------------------------------

_CCN_PATTERN = re.compile(r"\b(\d{4,6})\b")
_HOSP_PATTERN = re.compile(r"HOSP[_\s]*(\w+)", re.IGNORECASE)


def extract_hospital_code(text: str) -> Optional[str]:
    """
    Extract hospital identifier from user prompt.
    Supports:
    - Standard Medicare CCN (4-6 digits, e.g. 10001, 050001)
    - Legacy HOSP_<id> format
    """
    ccn_match = _CCN_PATTERN.search(text)
    if ccn_match:
        return ccn_match.group(1)

    hosp_match = _HOSP_PATTERN.search(text)
    if hosp_match:
        val = hosp_match.group(1).upper()
        return val if val.isdigit() else f"HOSP_{val}"

    return None


# ---------------------------------------------------------------------------
# DB context fetching
# ---------------------------------------------------------------------------


def fetch_agent_context(db: Session, hospital_code: str) -> Dict[str, Any]:
    """
    Pull complete data required for operational analysis:
    - 4-week dual-target forecasts (admissions + inpatient beds used)
    - Safe capacity threshold (85%) & resource gap
    - Recent historical admissions
    - Exogenous telemetry (AQI, temperature, outbreak, mobility)
    """

    # 1. Resolve hospital (by hospital_id or name search)
    hospital: Optional[Hospital] = (
        db.query(Hospital)
        .filter(
            or_(
                Hospital.hospital_id == hospital_code,
                Hospital.hospital_id == hospital_code.lstrip("0"),
                Hospital.name.ilike(f"%{hospital_code}%"),
            )
        )
        .first()
    )
    if hospital is None:
        # Fallback to first hospital if requested code does not exist
        hospital = db.query(Hospital).first()

    if hospital is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hospital '{hospital_code}' not found in the database.",
        )

    # 2. Latest 4-week dual-target forecasts
    latest_run: Optional[ForecastRun] = (
        db.query(ForecastRun)
        .order_by(desc(ForecastRun.created_at))
        .first()
    )
    forecasts: List[Dict[str, Any]] = []
    if latest_run:
        rows = (
            db.query(Forecast)
            .filter(
                Forecast.forecast_run_id == latest_run.id,
                Forecast.hospital_id == hospital.id,
            )
            .order_by(Forecast.target, Forecast.horizon)
            .all()
        )
        forecasts = [
            {
                "target": f.target,
                "horizon": f.horizon,
                "prediction": round(f.prediction, 1),
                "prediction_low": round(f.prediction_low, 1) if f.prediction_low is not None else None,
                "prediction_high": round(f.prediction_high, 1) if f.prediction_high is not None else None,
                "resource_gap": round(f.resource_gap, 1) if f.resource_gap is not None else None,
                "capacity_source": f.capacity_source,
                "date": str(f.forecast_date),
            }
            for f in rows
        ]

    # Flag hospitals with no forecast data (newly added, not in training set)
    has_forecast_data = len(forecasts) > 0

    # 3. Most recent admission records
    admissions_rows = (
        db.query(AdmissionHistory)
        .filter(AdmissionHistory.hospital_id == hospital.id)
        .order_by(desc(AdmissionHistory.date))
        .limit(14)
        .all()
    )
    admissions = [
        {"date": str(a.date), "admissions": a.admissions}
        for a in admissions_rows
    ]

    # 4. Latest external signal
    signal_row: Optional[ExternalSignal] = (
        db.query(ExternalSignal)
        .filter(ExternalSignal.hospital_id == hospital.id)
        .order_by(desc(ExternalSignal.date))
        .first()
    )
    external_signal: Dict[str, Any] = {}
    if signal_row:
        external_signal = {
            "date": str(signal_row.date),
            "temperature": signal_row.temperature,
            "aqi": signal_row.aqi,
            "outbreak_index": signal_row.outbreak_index,
            "mobility_index": signal_row.mobility_index,
        }

    return {
        "hospital_name": hospital.name or hospital.hospital_id,
        "hospital_code": hospital.hospital_id,
        "capacity": hospital.capacity or 200,
        "icu_capacity": hospital.icu_capacity or 20,
        "region": hospital.region or "Unknown",
        "forecasts": forecasts,
        "has_forecast_data": has_forecast_data,
        "admissions": admissions,
        "external_signal": external_signal,
    }


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_MESSAGE = (
    "You are an expert Hospital Operations & Capacity Intelligence Analyst. "
    "Hospital executives and chief medical officers rely on your operational briefings.\n\n"
    "GUIDELINES:\n"
    "1. Structure your answer with clear headers: ### 1. 4-Week Trend Analysis, ### 2. Risk & Capacity Drivers, ### 3. Actionable Staffing & Bed Recommendations.\n"
    "2. Be concise, clinical, and precise. Cite exact predicted bed occupancy numbers, quantile intervals, and admissions.\n"
    "3. Highlight safe capacity thresholds (85% safe capacity standard).\n"
    "4. Connect environmental/outbreak signals (AQI, temperature, outbreak index) to anticipated patient volume.\n"
    "5. Keep total length under 300 words. Avoid fluff."
)


def build_prompt(context: Dict[str, Any], question: str) -> str:
    """Assemble the grounded user message from DB context and user question."""

    forecasts = context["forecasts"]
    bed_fcs = [f for f in forecasts if f.get("target") == "inpatient_beds_used"]
    adm_fcs = [f for f in forecasts if f.get("target") == "admissions"]

    # Format bed forecasts
    bed_lines = "\n".join(
        f"  Week {f['horizon']} ({f['date']}): {f['prediction']} beds used "
        f"[80% CI: {f.get('prediction_low', 'N/A')} - {f.get('prediction_high', 'N/A')}], "
        f"Capacity Gap vs 85%: {f.get('resource_gap', 0):+.1f} beds"
        for f in bed_fcs
    ) or "  (no bed occupancy forecast recorded)"

    # Format admission forecasts
    adm_lines = "\n".join(
        f"  Week {f['horizon']} ({f['date']}): {f['prediction']} predicted admissions "
        f"[80% CI: {f.get('prediction_low', 'N/A')} - {f.get('prediction_high', 'N/A')}]"
        for f in adm_fcs
    ) or "  (no admission demand forecast recorded)"

    # Admissions history
    admissions = context["admissions"]
    admission_lines = "\n".join(
        f"  {a['date']}: {a['admissions']} admissions"
        for a in admissions[:6]
    ) or "  (no recent historical records)"

    # Telemetry signals
    sig = context.get("external_signal", {})
    if sig:
        signal_block = (
            f"  Date: {sig.get('date', 'N/A')}\n"
            f"  Temperature: {sig.get('temperature', 'N/A')} C\n"
            f"  AQI: {sig.get('aqi', 'N/A')}\n"
            f"  Outbreak index: {sig.get('outbreak_index', 0)} (0=normal, 1=severe)\n"
            f"  Mobility index: {sig.get('mobility_index', 1.0)}"
        )
    else:
        signal_block = "  (standard seasonal baselines)"

    capacity = context.get("capacity") or 200
    safe_capacity = round(capacity * 0.85, 1)

    return (
        f"Facility: {context['hospital_name']} (CCN: {context['hospital_code']})\n"
        f"State/Region: {context.get('region', 'N/A')}\n"
        f"Total Licensed Beds: {capacity} | Safe Operating Limit (85%): {safe_capacity} beds | ICU: {context.get('icu_capacity', 20)} beds\n"
        f"\n"
        f"=== Dual-Target 4-Week Horizon Forecast ===\n"
        f"Occupancy (Inpatient Beds Used):\n{bed_lines}\n\n"
        f"Demand (Admissions):\n{adm_lines}\n"
        f"\n"
        f"=== Recent Historical Admissions ===\n{admission_lines}\n"
        f"\n"
        f"=== Exogenous Telemetry & Environmental Signals ===\n{signal_block}\n"
        f"\n"
        f"USER QUESTION: {question}\n"
    )


# ---------------------------------------------------------------------------
# Groq API call
# ---------------------------------------------------------------------------


def call_groq(system_msg: str, user_msg: str) -> tuple[str, float]:
    """
    Call the Groq Chat Completions API synchronously via httpx.

    Returns (analysis_text, inference_seconds).
    Raises HTTPException on failure.
    """
    api_key = _get_groq_api_key()
    model = _get_groq_model()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent service unavailable: GROQ_API_KEY is not configured.",
        )

    models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]
    start = time.time()
    last_status = 502
    last_err_text = ""

    try:
        for cand_model in models_to_try:
            payload = {
                "model": cand_model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.3,
                "max_tokens": 700,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(GROQ_API_URL, json=payload, headers=headers)

                if resp.status_code == 404:
                    logger.warning(f"[AGENT] Model '{cand_model}' returned 404 on Groq. Trying fallback model...")
                    last_status = 404
                    last_err_text = resp.text
                    continue

                if resp.status_code != 200:
                    logger.error(
                        f"[AGENT] Groq API error {resp.status_code} on model {cand_model}: {resp.text[:300]}"
                    )
                    last_status = resp.status_code
                    last_err_text = resp.text
                    continue

                data = resp.json()
                analysis = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if not analysis:
                    continue

                elapsed = round(time.time() - start, 3)
                logger.info(
                    f"[AGENT] Groq response OK | model={cand_model} | "
                    f"tokens_in={data.get('usage', {}).get('prompt_tokens', '?')} | "
                    f"tokens_out={data.get('usage', {}).get('completion_tokens', '?')} | "
                    f"time={elapsed}s"
                )
                return analysis, elapsed

            except httpx.TimeoutException:
                elapsed = round(time.time() - start, 3)
                logger.error(f"[AGENT] Groq API timed out after {elapsed}s on model {cand_model}")
                continue

        elapsed = round(time.time() - start, 3)
        logger.error(f"[AGENT] All Groq models failed. Last status: {last_status} - {last_err_text[:200]}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Groq API returned {last_status}. Please try again later.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        elapsed = round(time.time() - start, 3)
        logger.error(f"[AGENT] Groq API unexpected error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach Groq API. Please try again later.",
        )

