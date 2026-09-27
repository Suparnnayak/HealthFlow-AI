from typing import Optional
from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    """Request body for POST /agent/query."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural-language question about a hospital forecast.",
        examples=[
            "Why is 10001 bed occupancy increasing over the next 4 weeks?",
            "Explain the admission trend for 10017",
        ],
    )
    hospital_id: Optional[str] = Field(
        None,
        description="Optional hospital ID (e.g. 10001). If omitted, extracted from question text or resolved from user profile.",
    )


class AgentQueryResponse(BaseModel):
    """Response body for POST /agent/query."""

    hospital: str = Field(..., description="Resolved hospital code")
    analysis: str = Field(..., description="LLM-generated analysis grounded in DB data")
    inference_time_seconds: float = Field(
        ..., description="Wall-clock time for the Groq API call"
    )

