"""
Agent router — POST /agent/query

Accepts a natural-language question that mentions a hospital code (HOSP_<n>),
fetches real DB data as context, and returns an LLM-generated analysis
from the Groq API.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.session import get_db
from app.dependencies import get_current_user
from app.agent.schemas import AgentQueryRequest, AgentQueryResponse
from app.agent.service import (
    extract_hospital_code,
    fetch_agent_context,
    build_prompt,
    call_groq,
    SYSTEM_MESSAGE,
)
from forecast_system.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/query", response_model=AgentQueryResponse)
def agent_query(
    body: AgentQueryRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    POST /agent/query

    Workflow:
        1. Extract hospital code from the question text
        2. Pull structured context from the database
        3. Build a grounded prompt (system + user message)
        4. Call Groq Chat Completions API
        5. Return the analysis

    Requires authentication (Bearer token).
    """

    # --- 1. Extract hospital code ---
    hospital_code = (body.hospital_id or "").strip()
    if not hospital_code:
        hospital_code = extract_hospital_code(body.question)
    if not hospital_code:
        # Check if staff user has an assigned hospital
        if current_user.role != "admin":
            allowed_ids = [a.hospital_id for a in current_user.hospital_access]
            hospital_code = allowed_ids[0] if allowed_ids else "10001"
        else:
            hospital_code = "10001"

    # Check hospital access permissions
    if current_user.role != "admin":
        allowed_ids = [a.hospital_id for a in current_user.hospital_access]
        if allowed_ids and hospital_code not in allowed_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to hospital {hospital_code}. Your assigned facility is {allowed_ids[0]}.",
            )

    from app.core.access_logger import log_access
    log_access(
        user_id=str(current_user.id),
        hospital_id=hospital_code,
        endpoint="/agent/query",
        query_params={"question": body.question[:100]},
    )

    logger.info(
        f"[AGENT] Query from user={current_user.email} | "
        f"hospital={hospital_code} | q={body.question[:80]}"
    )

    # --- 2. Fetch DB context ---
    context = fetch_agent_context(db, hospital_code)

    # --- 2b. Guard: no forecast data (hospital not in training set) ---
    if not context.get("has_forecast_data"):
        no_data_msg = (
            f"**No Forecast Data Available for {context['hospital_name']} ({context['hospital_code']})**\n\n"
            f"This facility was recently added to the system but was not included in the model's training dataset "
            f"(the current ModelBundleV2 was trained on 1,489 HHS-reported hospitals). "
            f"No precomputed 4-week forecasts, admission history, or external signal telemetry are available yet.\n\n"
            f"**To generate forecasts for this facility, an admin must:**\n"
            f"1. Collect at least 8 weeks of weekly inpatient census data for CCN {context['hospital_code']}\n"
            f"2. Retrain ModelBundleV2 to include this facility's historical patterns\n"
            f"3. Re-run the weekly forecast job after retraining\n\n"
            f"Until then, this AI analyst cannot generate reliable operational guidance for this facility."
        )
        return AgentQueryResponse(
            hospital=hospital_code,
            analysis=no_data_msg,
            inference_time_seconds=0.0,
        )

    # --- 3. Build prompt ---
    user_message = build_prompt(context, body.question)

    # --- 4. Call Groq ---
    analysis, elapsed = call_groq(SYSTEM_MESSAGE, user_message)

    # --- 5. Return ---
    return AgentQueryResponse(
        hospital=hospital_code,
        analysis=analysis,
        inference_time_seconds=elapsed,
    )

