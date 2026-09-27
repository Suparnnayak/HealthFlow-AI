"""
Forecast Job (Serving Path)

NOTE ON CADENCE DECISION:
The V2 forecasting model operates on a weekly horizon (1-4 weeks ahead) based on
weekly hospital reporting data (NHSN/HHS collection weeks). 
This script delegates directly to `scripts.weekly_forecast_job.run_weekly_forecast_job`
to ensure complete backward compatibility with existing cron workflows / CI triggers,
while enforcing weekly horizon semantics (horizons: 1, 2, 3, 4 weeks) and dual-target
prediction (admissions + inpatient_beds_used with quantile intervals).
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.weekly_forecast_job import run_weekly_forecast_job


def main() -> int:
    print("[INFO] Invoking weekly forecast job (V2 weekly dual-target model) ...")
    return run_weekly_forecast_job()


if __name__ == "__main__":
    sys.exit(main())
