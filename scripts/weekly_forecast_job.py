"""
Weekly Forecast Job — Precomputed Dual-Target Forecasts (ModelBundleV2)

Standalone script that:
  1. Loads ModelBundleV2 from disk
  2. Loads hospital history and metadata
  3. Computes 4-week moving average (roll_mean_4) baselines and lag features
  4. Generates point, 10th-percentile (low), and 90th-percentile (high) forecasts
     for both 'admissions' and 'inpatient_beds_used' across horizons [1, 2, 3, 4] weeks
  5. Applies capacity guarding with historical median fallback for non-positive capacities
  6. Computes resource gap and records capacity_source ("reported" | "historical_median_fallback")
  7. UPSERTs forecasts into PostgreSQL 'forecasts' table and creates a 'forecast_runs' record

Cadence: Weekly (aligned with weekly NHSN data granularity and 1-4w forecast horizons).
"""

import sys
import os
import time
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import pandas as pd

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.session import SessionLocal
from database import crud
from database.models import Hospital, ForecastRun
from forecast_system.model_bundle_v2 import ModelBundleV2
from forecast_system.resource_gap import compute_hospital_median_capacities, compute_guarded_resource_gap
from scripts.retrain_v2 import (
    load_and_parse,
    build_features_for_target,
    CSV_PATH,
    TARGETS,
    HORIZONS,
)
from forecast_system.utils import get_logger

logger = get_logger(__name__)

BUNDLE_PATH = PROJECT_ROOT / "models" / "forecast_system" / "model_bundle_v2.pkl"


def run_weekly_forecast_job() -> int:
    start_time = time.time()
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] Weekly Forecast Job (ModelBundleV2) starting ...")

    # 1. Load ModelBundleV2
    if not BUNDLE_PATH.exists():
        print(f"FATAL: ModelBundleV2 not found at {BUNDLE_PATH}")
        return 1

    print(f"  Loading ModelBundleV2 from {BUNDLE_PATH} ...")
    bundle = ModelBundleV2.load(str(BUNDLE_PATH))
    model_version = bundle.metadata.get("version", "2.0.0")
    print(f"  Model loaded: Version {model_version}, targets={bundle.TARGETS}, horizons={bundle.HORIZONS}")

    # 2. Load and parse dataset
    if not CSV_PATH.exists():
        print(f"FATAL: Dataset CSV not found at {CSV_PATH}")
        return 1

    print(f"  Loading dataset for feature extraction ...")
    df_raw = load_and_parse(CSV_PATH)
    median_caps = compute_hospital_median_capacities(df_raw, ccn_col="ccn", capacity_col="hospital_capacity")
    print(f"  Computed historical median capacity for {len(median_caps)} hospitals.")

    # 3. Synchronize / Ensure hospitals exist in DB
    db = SessionLocal()
    try:
        # Get unique hospitals from dataset to ensure DB is populated
        hospital_records = (
            df_raw[["ccn", "hospital_name", "state", "hospital_capacity", "icu_capacity"]]
            .drop_duplicates(subset=["ccn"], keep="last")
        )
        print(f"  Syncing {len(hospital_records)} hospitals into database ...")
        for _, h_row in hospital_records.iterrows():
            ccn_str = str(h_row["ccn"])
            crud.get_or_create_hospital(
                db=db,
                hospital_id=ccn_str,
                name=h_row.get("hospital_name"),
                region=str(h_row.get("state")),
                capacity=int(h_row.get("hospital_capacity") or 0),
                icu_capacity=int(h_row.get("icu_capacity") or 0),
            )
        db.commit()

        # 4. Generate forecasts for latest state of each hospital
        all_forecast_rows: List[Dict[str, Any]] = []
        hospital_id_set = set()

        # Build latest state per target
        target_forecasts: Dict[str, Dict[int, pd.DataFrame]] = {}

        for target in TARGETS:
            print(f"  Building features for target: {target} ...")
            df_feat = build_features_for_target(df_raw, target)
            baseline_col = f"{target}_roll_mean_4_baseline"

            # Get the latest row per hospital (most recent collection_week)
            latest_idx = df_feat.groupby("ccn", observed=True)["collection_week"].idxmax()
            latest_df = df_feat.loc[latest_idx].copy().reset_index(drop=True)
            print(f"    Target {target}: {len(latest_df)} hospitals ready for prediction at latest week.")

            for h in HORIZONS:
                point_pred, low_pred, high_pred = bundle.predict(
                    target=target,
                    horizon=h,
                    X=latest_df,
                    roll_mean_4=latest_df[baseline_col],
                )

                sub = latest_df[["ccn", "collection_week", "hospital_capacity"]].copy()
                sub["horizon"] = h
                sub["target"] = target
                sub["prediction"] = point_pred
                sub["prediction_low"] = low_pred
                sub["prediction_high"] = high_pred

                if target not in target_forecasts:
                    target_forecasts[target] = {}
                target_forecasts[target][h] = sub

        # Merge targets and compute resource gap for inpatient_beds_used
        print("  Formatting forecasts and computing guarded resource gaps ...")
        for h in HORIZONS:
            adm_df = target_forecasts["admissions"][h]
            beds_df = target_forecasts["inpatient_beds_used"][h]

            # Process admissions
            for _, row in adm_df.iterrows():
                ccn_str = str(row["ccn"])
                hospital_id_set.add(ccn_str)
                base_dt = pd.to_datetime(row["collection_week"]).date()
                f_date = base_dt + timedelta(weeks=h)

                all_forecast_rows.append(
                    {
                        "hospital_id": ccn_str,
                        "target": "admissions",
                        "horizon": h,
                        "prediction": round(float(row["prediction"]), 2),
                        "prediction_low": round(float(row["prediction_low"]), 2),
                        "prediction_high": round(float(row["prediction_high"]), 2),
                        "resource_gap": None,
                        "capacity_source": None,
                        "forecast_date": f_date,
                    }
                )

            # Process inpatient_beds_used (with resource gap calculation)
            for _, row in beds_df.iterrows():
                ccn_str = str(row["ccn"])
                hospital_id_set.add(ccn_str)
                base_dt = pd.to_datetime(row["collection_week"]).date()
                f_date = base_dt + timedelta(weeks=h)

                # Compute guarded resource gap
                rg_info = compute_guarded_resource_gap(
                    predicted_beds=float(row["prediction"]),
                    reported_capacity=float(row["hospital_capacity"]) if pd.notna(row["hospital_capacity"]) else None,
                    hospital_id=ccn_str,
                    median_capacities=median_caps,
                )

                all_forecast_rows.append(
                    {
                        "hospital_id": ccn_str,
                        "target": "inpatient_beds_used",
                        "horizon": h,
                        "prediction": round(float(row["prediction"]), 2),
                        "prediction_low": round(float(row["prediction_low"]), 2),
                        "prediction_high": round(float(row["prediction_high"]), 2),
                        "resource_gap": rg_info["resource_gap"],
                        "capacity_source": rg_info["capacity_source"],
                        "forecast_date": f_date,
                    }
                )

        inference_time = time.time() - start_time
        print(f"  Generated {len(all_forecast_rows)} total forecast records across {len(hospital_id_set)} hospitals.")

        # 5. Create forecast_run record
        latest_coll_week = df_raw["collection_week"].max().date()
        forecast_run = crud.create_forecast_run(
            db=db,
            hospital_count=len(hospital_id_set),
            horizon_count=len(HORIZONS),
            total_forecasts=len(all_forecast_rows),
            inference_time_seconds=inference_time,
            model_version=model_version,
            signal_date_used=latest_coll_week,
        )
        run_id = forecast_run.id
        print(f"  Created forecast_run: {run_id}")

        # 6. Batch UPSERT into database
        print(f"  Writing forecasts to PostgreSQL in chunks ...")
        chunk_size = 5000
        for i in range(0, len(all_forecast_rows), chunk_size):
            chunk = all_forecast_rows[i : i + chunk_size]
            crud.create_forecasts_batch(
                db=db,
                forecast_run_id=run_id,
                forecasts_data=chunk,
            )
            db.commit()

        total_time = time.time() - start_time
        print(f"\n=== Weekly Forecast Job Completed Successfully ===")
        print(f"  Run ID            : {run_id}")
        print(f"  Model Version     : {model_version}")
        print(f"  Base Week         : {latest_coll_week}")
        print(f"  Hospitals         : {len(hospital_id_set)}")
        print(f"  Forecasts Upserted: {len(all_forecast_rows)}")
        print(f"  Total Duration    : {total_time:.2f}s\n")
        return 0

    except Exception as exc:
        db.rollback()
        logger.exception(f"Weekly forecast job failed: {exc}")
        print(f"FATAL: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(run_weekly_forecast_job())
