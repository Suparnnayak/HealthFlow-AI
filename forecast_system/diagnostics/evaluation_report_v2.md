# HealthFlow AI — V2 Evaluation Report

**Generated**: 2026-09-15T07:02:55.473628+00:00

## Dataset Summary

- **Source**: `cleaned_hospital_data.csv`
- **Total rows**: 309,060
- **Hospitals**: 1,489
- **Date range**: 2019-12-29 -> 2024-04-21
- **Admissions non-null**: 274,975 (89.0%)
- **Inpatient beds used non-null**: 288,575 (93.4%)
- **Modeling approach**: Residual-on-MA4 (predict deviation from 4-week moving average)
- **Horizons**: 1, 2, 3, 4 weeks ahead

## Target: `admissions`

| Horizon | Method | MAE | RMSE | MAPE (%) | Beats MA4? |
|---------|--------|-----|------|----------|------------|
| 1w | **LightGBM-residual** | 48.91 | 103.91 | 13.76 | ✗ No |
| 1w | MA4 baseline | 48.68 | 104.24 | 13.40 |  |
| 1w | Naive persistence | 53.28 | 110.97 | 13.93 |  |
| 2w | **LightGBM-residual** | 52.01 | 110.96 | 14.88 | ✗ No |
| 2w | MA4 baseline | 51.46 | 110.87 | 14.35 |  |
| 2w | Naive persistence | 56.28 | 119.07 | 14.98 |  |
| 3w | **LightGBM-residual** | 54.41 | 115.91 | 15.84 | ✗ No |
| 3w | MA4 baseline | 53.74 | 115.86 | 15.23 |  |
| 3w | Naive persistence | 58.40 | 122.62 | 15.63 |  |
| 4w | **LightGBM-residual** | 56.36 | 120.33 | 16.77 | ✗ No |
| 4w | MA4 baseline | 55.59 | 120.38 | 15.96 |  |
| 4w | Naive persistence | 61.44 | 129.17 | 16.91 |  |

**Prediction Interval Coverage (10th–90th percentile):**

- Horizon 1w: 82.1%
- Horizon 2w: 81.8%
- Horizon 3w: 82.0%
- Horizon 4w: 82.9%

> **⚠ Note**: The LightGBM-residual model does NOT beat the plain MA4 baseline for `admissions` at horizon(s) [1, 2, 3, 4]. The moving-average baseline is the better predictor at those horizons.

### By Hospital-Size Tier (`admissions`)

| Horizon | Tier | Model MAE | MA4 MAE | Naive MAE | N |
|---------|------|-----------|---------|-----------|---|
| 1w | small | 14.10 | 12.86 | 14.01 | 12,785 |
| 1w | medium | 42.31 | 42.30 | 46.00 | 13,406 |
| 1w | large | 87.20 | 87.70 | 96.31 | 13,934 |
| 2w | small | 15.21 | 13.57 | 14.94 | 12,731 |
| 2w | medium | 45.15 | 44.82 | 48.99 | 13,365 |
| 2w | large | 92.30 | 92.55 | 101.13 | 13,902 |
| 3w | small | 16.01 | 14.10 | 15.55 | 12,587 |
| 3w | medium | 47.30 | 46.91 | 50.72 | 13,233 |
| 3w | large | 96.51 | 96.70 | 105.11 | 13,720 |
| 4w | small | 16.87 | 14.52 | 16.07 | 12,446 |
| 4w | medium | 49.29 | 48.75 | 53.58 | 13,061 |
| 4w | large | 99.43 | 99.90 | 110.69 | 13,551 |

## Target: `inpatient_beds_used`

| Horizon | Method | MAE | RMSE | MAPE (%) | Beats MA4? |
|---------|--------|-----|------|----------|------------|
| 1w | **LightGBM-residual** | 6.62 | 12.08 | 10.41 | ✓ Yes |
| 1w | MA4 baseline | 6.78 | 12.42 | 10.37 |  |
| 1w | Naive persistence | 7.41 | 13.41 | 11.27 |  |
| 2w | **LightGBM-residual** | 6.98 | 12.88 | 10.91 | ✓ Yes |
| 2w | MA4 baseline | 7.16 | 13.23 | 10.88 |  |
| 2w | Naive persistence | 7.86 | 14.32 | 12.01 |  |
| 3w | **LightGBM-residual** | 7.30 | 13.52 | 11.33 | ✓ Yes |
| 3w | MA4 baseline | 7.52 | 13.94 | 11.29 |  |
| 3w | Naive persistence | 8.11 | 14.88 | 12.38 |  |
| 4w | **LightGBM-residual** | 7.60 | 14.10 | 11.70 | ✓ Yes |
| 4w | MA4 baseline | 7.86 | 14.56 | 11.65 |  |
| 4w | Naive persistence | 8.37 | 15.33 | 12.80 |  |

**Prediction Interval Coverage (10th–90th percentile):**

- Horizon 1w: 80.1%
- Horizon 2w: 80.4%
- Horizon 3w: 78.9%
- Horizon 4w: 81.4%

> **✓** The LightGBM-residual model beats the MA4 baseline at all horizons for `inpatient_beds_used`.

### By Hospital-Size Tier (`inpatient_beds_used`)

| Horizon | Tier | Model MAE | MA4 MAE | Naive MAE | N |
|---------|------|-----------|---------|-----------|---|
| 1w | small | 2.55 | 2.46 | 2.59 | 12,172 |
| 1w | medium | 5.22 | 5.33 | 5.83 | 14,740 |
| 1w | large | 11.27 | 11.68 | 12.85 | 15,080 |
| 2w | small | 2.67 | 2.61 | 2.83 | 12,097 |
| 2w | medium | 5.51 | 5.63 | 6.20 | 14,690 |
| 2w | large | 11.87 | 12.33 | 13.54 | 15,024 |
| 3w | small | 2.79 | 2.71 | 2.95 | 12,026 |
| 3w | medium | 5.72 | 5.85 | 6.39 | 14,567 |
| 3w | large | 12.48 | 13.03 | 13.97 | 14,901 |
| 4w | small | 2.90 | 2.80 | 3.04 | 11,930 |
| 4w | medium | 5.90 | 6.07 | 6.60 | 14,487 |
| 4w | large | 13.05 | 13.68 | 14.39 | 14,847 |

## Resource Gap (85% Capacity Threshold)

Computed as: `resource_gap = forecasted_inpatient_beds_used - (hospital_capacity × 0.85)`

| Horizon | Exceeding | Total | % Exceeding | Mean Gap | Max Gap |
|---------|-----------|-------|-------------|----------|---------|
| 1w | 4,909 | 41,992 | 11.7% | 20.6 | 660.6 |
| 2w | 4,852 | 41,811 | 11.6% | 20.6 | 661.5 |
| 3w | 4,788 | 41,494 | 11.5% | 20.7 | 664.0 |
| 4w | 4,764 | 41,264 | 11.6% | 20.7 | 665.7 |

## Top 20 Features — `admissions`

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | admissions_roll_std_4 | 71 |
| 2 | ccn | 69 |
| 3 | week_of_year | 56 |
| 4 | admissions_lag_4 | 55 |
| 5 | admissions_roll_std_8 | 38 |
| 6 | hospital_capacity | 32 |
| 7 | icu_capacity | 32 |
| 8 | state | 28 |
| 9 | admissions_roll_mean_4 | 26 |
| 10 | admissions_lag_1 | 18 |
| 11 | admissions_lag_8 | 17 |
| 12 | admissions_lag_2 | 16 |
| 13 | lat | 13 |
| 14 | lon | 11 |
| 15 | month | 9 |
| 16 | admissions_roll_mean_8 | 8 |
| 17 | admissions_roll_mean_4_baseline | 6 |
| 18 | hospital_subtype | 1 |
| 19 | is_metro_micro | 0 |

## Top 20 Features — `inpatient_beds_used`

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | ccn | 886 |
| 2 | inpatient_beds_used_roll_std_8 | 585 |
| 3 | week_of_year | 582 |
| 4 | inpatient_beds_used_roll_std_4 | 489 |
| 5 | inpatient_beds_used_lag_4 | 468 |
| 6 | hospital_capacity | 316 |
| 7 | icu_capacity | 308 |
| 8 | state | 204 |
| 9 | inpatient_beds_used_roll_mean_4 | 180 |
| 10 | inpatient_beds_used_lag_2 | 180 |
| 11 | month | 178 |
| 12 | inpatient_beds_used_lag_8 | 173 |
| 13 | lat | 134 |
| 14 | inpatient_beds_used_roll_mean_8 | 127 |
| 15 | lon | 109 |
| 16 | inpatient_beds_used_lag_1 | 96 |
| 17 | inpatient_beds_used_roll_mean_4_baseline | 31 |
| 18 | hospital_subtype | 5 |
| 19 | is_metro_micro | 0 |

## Data Quality & Stated Limitations

1. **Dependence on External Reported Capacity**: Resource-gap statistics depend directly on hospital capacity values reported in the HHS COVID-19/CMS weekly datasets.
2. **Capacity Guard for Missing/Non-Positive Values**: Facilities with reported `hospital_capacity <= 0` or `NaN` automatically fall back to the hospital's historical non-zero median capacity (`capacity_source: "historical_median_fallback"`). This guards against spurious deficits (e.g. eliminating the 928-bed phantom deficit for facilities reporting 0 capacity).
3. **Residual Anomaly Limitation (Low-but-Positive Capacity)**: Certain facilities exhibit reporting regime shifts where positive capacity values drop severely below operational reality without hitting zero. For example, UC San Diego Health Hillcrest (CCN `050025`, historical median ~839.3 beds) reported ~73–119 beds for 33 consecutive weeks following the May 2023 end of the federal Public Health Emergency, while maintaining ~700+ inpatient beds used. The system incorporates an anomaly guard threshold (`ANOMALOUS_LOW_CAPACITY_RATIO = 0.35`) to explicitly flag these records (`capacity_source: "reported_anomalous_low"`). In un-imputed evaluations, these rows represent a known residual limitation in external reporting that accounts for dataset-wide maximum gap outliers.

## ⚠ Production Wiring Notes

The retrained model uses **weekly** horizons (1–4 weeks), not the existing **daily** horizons (1–7 days). Wiring this into `daily_forecast_job.py` requires:

1. Change `HORIZONS = [1,2,3,4,5,6,7]` -> `[1,2,3,4]`
2. Change `timedelta(days=horizon)` -> `timedelta(weeks=horizon)` for `forecast_date`
3. Update the `ForecastRequest` validator (`horizon must be <= 7` -> `<= 4`)
4. Update frontend chart labels from "Day 1–7" to "Week 1–4"
5. Load `ModelBundleV2` instead of `ModelBundle`
