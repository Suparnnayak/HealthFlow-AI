"""
Resource Gap & Capacity Guard Utilities

Computes:
  resource_gap = predicted_inpatient_beds_used - (hospital_capacity * 0.85)

Guards against non-positive/missing hospital capacity (hospital_capacity <= 0 or NaN).
Falls back to the hospital's historical median capacity computed from non-zero records,
logs a warning, and annotates capacity_source:
  - "reported"
  - "historical_median_fallback"
"""

import logging
from typing import Dict, Tuple, Optional, Any
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_hospital_median_capacities(df: pd.DataFrame, ccn_col: str = "ccn", capacity_col: str = "hospital_capacity") -> Dict[str, float]:
    """
    Compute each hospital's median capacity from rows where capacity > 0.
    Returns dict mapping ccn/hospital_id -> median_capacity.
    """
    valid = df[df[capacity_col] > 0]
    if valid.empty:
        return {}
    
    medians = valid.groupby(ccn_col, observed=True)[capacity_col].median()
    return {str(ccn): float(val) for ccn, val in medians.items()}


# Threshold below which reported positive capacity is flagged as an anomalous low-capacity outlier
ANOMALOUS_LOW_CAPACITY_RATIO = 0.35


def get_guarded_capacity(
    hospital_id: str,
    reported_capacity: Optional[float],
    median_capacities: Dict[str, float],
    default_fallback: float = 100.0,
    anomaly_threshold_ratio: float = ANOMALOUS_LOW_CAPACITY_RATIO,
) -> Tuple[float, str]:
    """
    Validate reported capacity and return (effective_capacity, capacity_source).
    
    1. If reported_capacity is <= 0, NaN, or None:
      - Falls back to hospital's own historical median (if > 0)
      - Otherwise falls back to global default
      - Logs a warning
      - Sets capacity_source = "historical_median_fallback"
      
    2. If reported_capacity is positive but < anomaly_threshold_ratio * historical_median:
      - Preserves reported capacity as effective_capacity
      - Flags capacity_source = "reported_anomalous_low"
      - Logs a warning indicating a potential departmental/reporting glitch
      
    3. Otherwise:
      - Returns (reported_capacity, "reported")
    """
    h_str = str(hospital_id)
    is_invalid = reported_capacity is None or pd.isna(reported_capacity) or reported_capacity <= 0

    if not is_invalid:
        rep_val = float(reported_capacity)
        median_val = median_capacities.get(h_str)
        if median_val is not None and median_val > 0 and rep_val < anomaly_threshold_ratio * median_val:
            logger.warning(
                f"[CAPACITY ANOMALY] Hospital {h_str} reported capacity {rep_val:.1f} beds is below "
                f"{anomaly_threshold_ratio*100:.0f}% of its historical median ({median_val:.1f} beds). "
                f"Flagged as reported_anomalous_low."
            )
            return rep_val, "reported_anomalous_low"
        return rep_val, "reported"

    # Fallback needed for invalid (<= 0 or NaN)
    fallback = median_capacities.get(h_str)
    if fallback is None or fallback <= 0 or pd.isna(fallback):
        fallback = default_fallback

    logger.warning(
        f"[CAPACITY FALLBACK] Hospital {h_str} has invalid capacity ({reported_capacity}). "
        f"Falling back to historical median capacity: {fallback:.1f} beds."
    )
    return float(fallback), "historical_median_fallback"


def compute_guarded_resource_gap(
    predicted_beds: float,
    reported_capacity: Optional[float],
    hospital_id: str,
    median_capacities: Dict[str, float],
    threshold_ratio: float = 0.85,
) -> Dict[str, Any]:
    """
    Compute safe capacity, resource gap, and whether safe capacity is exceeded.
    """
    effective_cap, source = get_guarded_capacity(hospital_id, reported_capacity, median_capacities)
    safe_capacity = effective_cap * threshold_ratio
    gap = float(predicted_beds - safe_capacity)
    exceeds = bool(gap > 0)

    return {
        "hospital_id": str(hospital_id),
        "effective_capacity": round(effective_cap, 2),
        "safe_capacity": round(safe_capacity, 2),
        "resource_gap": round(gap, 2),
        "exceeds_safe_capacity": exceeds,
        "capacity_source": source,
    }
