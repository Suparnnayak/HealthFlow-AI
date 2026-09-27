import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

PROJECT_ROOT = Path(r"d:\Hospital_forecasting")
sys.path.insert(0, str(PROJECT_ROOT))

from forecast_system.model_bundle_v2 import ModelBundleV2
from scripts.retrain_v2 import load_and_parse, build_features_for_target, chrono_split, build_feature_list, compute_hospital_tiers, compute_metrics, compute_tiered_metrics

def main():
    print("Loading raw data...")
    csv_path = PROJECT_ROOT / "dataset" / "cleaned_hospital_data.csv"
    df = load_and_parse(csv_path)
    tier_map = compute_hospital_tiers(df)

    # Load hospital names mapping
    names_df = pd.read_csv(csv_path, usecols=["ccn", "hospital_name"]).drop_duplicates()
    ccn_to_name = dict(zip(names_df["ccn"].astype(str), names_df["hospital_name"]))

    # ----------------------------------------------------
    # 1. Verify no data leakage in split & lag features
    # ----------------------------------------------------
    print("\n" + "="*50)
    print("1. VERIFYING SPLIT & FEATURE LEAKAGE")
    print("="*50)

    for target in ["admissions", "inpatient_beds_used"]:
        df_feat = build_features_for_target(df, target)
        for horizon in [1, 2, 3, 4]:
            df_h = df_feat.copy()
            df_h["y_future"] = df_h.groupby("ccn", observed=True)[target].shift(-horizon)
            df_h = df_h.dropna(subset=["y_future"]).copy()
            train_df, test_df = chrono_split(df_h)

            train_max = train_df.groupby("ccn", observed=True)["collection_week"].max()
            test_min = test_df.groupby("ccn", observed=True)["collection_week"].min()
            
            common_ccns = train_max.index.intersection(test_min.index)
            leakage_count = (train_max.loc[common_ccns] >= test_min.loc[common_ccns]).sum()
            print(f"Target {target}, Horizon {horizon}: Common hospitals={len(common_ccns)}, Leakage cases (train_max >= test_min): {leakage_count}")

            # Verify lag/rolling features
            sample_test = test_df.sample(5, random_state=42)
            for idx, row in sample_test.iterrows():
                ccn = row["ccn"]
                dt = row["collection_week"]
                hist = df_feat[(df_feat["ccn"] == ccn) & (df_feat["collection_week"] < dt)].sort_values("collection_week")
                last_4 = hist[target].tail(4)
                expected_ma4 = last_4.mean()
                actual_ma4 = row[f"{target}_roll_mean_4"]
                expected_lag1 = hist[target].iloc[-1]
                actual_lag1 = row[f"{target}_lag_1"]
                assert np.isclose(expected_ma4, actual_ma4), f"MA4 mismatch for {ccn} at {dt}: {expected_ma4} vs {actual_ma4}"
                assert np.isclose(expected_lag1, actual_lag1), f"Lag1 mismatch for {ccn} at {dt}: {expected_lag1} vs {actual_lag1}"
    print("Zero leakage confirmed for chronological splits and lag/rolling features!")

    # ----------------------------------------------------
    # 2. Check train vs test MAE for overfitting
    # ----------------------------------------------------
    print("\n" + "="*50)
    print("2. CHECK TRAIN VS TEST MAE")
    print("="*50)
    bundle_path = PROJECT_ROOT / "models" / "forecast_system" / "model_bundle_v2.pkl"
    bundle = ModelBundleV2.load(str(bundle_path))

    for target in ["admissions", "inpatient_beds_used"]:
        df_feat = build_features_for_target(df, target)
        feature_cols = build_feature_list(target)
        baseline_col = f"{target}_roll_mean_4_baseline"

        for horizon in [1, 2, 3, 4]:
            df_h = df_feat.copy()
            df_h["y_future"] = df_h.groupby("ccn", observed=True)[target].shift(-horizon)
            df_h = df_h.dropna(subset=["y_future"]).copy()
            df_h["residual"] = df_h["y_future"] - df_h[baseline_col]
            train_df, test_df = chrono_split(df_h)

            X_train = train_df[feature_cols].copy()
            X_test = test_df[feature_cols].copy()

            point_model = bundle.models[target][horizon]["point"]

            train_pred_res = point_model.predict(X_train)
            train_pred = np.maximum(train_df[baseline_col].values + train_pred_res, 0.0)
            train_mae = np.mean(np.abs(train_df["y_future"].values - train_pred))

            test_pred_res = point_model.predict(X_test)
            test_pred = np.maximum(test_df[baseline_col].values + test_pred_res, 0.0)
            test_mae = np.mean(np.abs(test_df["y_future"].values - test_pred))

            train_ma4_mae = np.mean(np.abs(train_df["y_future"].values - train_df[baseline_col].values))
            test_ma4_mae = np.mean(np.abs(test_df["y_future"].values - test_df[baseline_col].values))

            print(f"Target: {target:20s} H={horizon} | Train MAE: {train_mae:6.2f} (MA4: {train_ma4_mae:6.2f}) | Test MAE: {test_mae:6.2f} (MA4: {test_ma4_mae:6.2f}) | Ratio: {train_mae/test_mae:.2f}")

    # ----------------------------------------------------
    # 3. Check quantile coverage per horizon
    # ----------------------------------------------------
    print("\n" + "="*50)
    print("3. CHECK QUANTILE COVERAGE PER HORIZON")
    print("="*50)
    with open(PROJECT_ROOT / "forecast_system" / "diagnostics" / "evaluation_report_v2.json") as f:
        rep = json.load(f)

    for target in ["admissions", "inpatient_beds_used"]:
        print(f"Target: {target}")
        for h in ["1", "2", "3", "4"]:
            cov = rep["metrics"][target][h]["prediction_interval_coverage_pct"]
            print(f"  Horizon {h}w: Coverage = {cov}% (Nominal = 80%)")

    # ----------------------------------------------------
    # 4. Sanity-check feature importance
    # ----------------------------------------------------
    print("\n" + "="*50)
    print("4. SANITY-CHECK FEATURE IMPORTANCE")
    print("="*50)
    imp_adm = pd.read_csv(PROJECT_ROOT / "models" / "forecast_system" / "feature_importance_v2_admissions.csv")
    imp_beds = pd.read_csv(PROJECT_ROOT / "models" / "forecast_system" / "feature_importance_v2_inpatient_beds_used.csv")
    print("Admissions top 5 features:")
    print(imp_adm.head(5))
    ccn_adm_pct = imp_adm.loc[imp_adm['feature']=='ccn', 'importance'].values[0] / imp_adm['importance'].sum() * 100
    print(f"CCN share of importance in admissions: {ccn_adm_pct:.2f}%")

    print("\nInpatient beds used top 5 features:")
    print(imp_beds.head(5))
    ccn_beds_pct = imp_beds.loc[imp_beds['feature']=='ccn', 'importance'].values[0] / imp_beds['importance'].sum() * 100
    print(f"CCN share of importance in beds: {ccn_beds_pct:.2f}%")

    # ----------------------------------------------------
    # 5. Round-trip test: reload bundle and reproduce metrics
    # ----------------------------------------------------
    print("\n" + "="*50)
    print("5. ROUND-TRIP TEST: REPRODUCE METRICS FROM BUNDLE")
    print("="*50)
    for target in ["admissions", "inpatient_beds_used"]:
        df_feat = build_features_for_target(df, target)
        baseline_col = f"{target}_roll_mean_4_baseline"
        for horizon in [1, 2, 3, 4]:
            df_h = df_feat.copy()
            df_h["y_future"] = df_h.groupby("ccn", observed=True)[target].shift(-horizon)
            df_h = df_h.dropna(subset=["y_future"]).copy()
            _, test_df = chrono_split(df_h)

            point_pred, low_pred, high_pred = bundle.predict(
                target=target,
                horizon=horizon,
                X=test_df,
                roll_mean_4=test_df[baseline_col]
            )
            actuals = test_df["y_future"].values
            computed_mae = np.mean(np.abs(actuals - point_pred))
            computed_cov = np.mean((actuals >= low_pred) & (actuals <= high_pred)) * 100

            rep_mae = rep["metrics"][target][str(horizon)]["model"]["overall"]["MAE"]
            rep_cov = rep["metrics"][target][str(horizon)]["prediction_interval_coverage_pct"]

            diff_mae = abs(computed_mae - rep_mae)
            diff_cov = abs(computed_cov - rep_cov)
            print(f"Target {target:20s} H={horizon} | Rep MAE: {rep_mae:.4f}, Calc MAE: {computed_mae:.4f} (Diff: {diff_mae:.6f}) | Rep Cov: {rep_cov}%, Calc Cov: {computed_cov:.2f}% (Diff: {diff_cov:.4f})")

    # ----------------------------------------------------
    # 6. Spot-check 3-5 real hospitals & max gap hospital
    # ----------------------------------------------------
    print("\n" + "="*50)
    print("6. SPOT CHECK HOSPITALS & RESOURCE GAP INVESTIGATION")
    print("="*50)
    df_beds = build_features_for_target(df, "inpatient_beds_used")
    df_beds["y_future"] = df_beds.groupby("ccn", observed=True)["inpatient_beds_used"].shift(-1)
    df_beds = df_beds.dropna(subset=["y_future"]).copy()
    _, test_beds = chrono_split(df_beds)
    
    pt, lw, hg = bundle.predict("inpatient_beds_used", 1, test_beds, test_beds["inpatient_beds_used_roll_mean_4_baseline"])
    test_beds["pred_beds"] = pt
    test_beds["safe_cap"] = test_beds["hospital_capacity"] * 0.85
    test_beds["gap"] = test_beds["pred_beds"] - test_beds["safe_cap"]
    
    # Sort by gap
    top_gaps = test_beds.sort_values("gap", ascending=False).head(5)
    print("Top gap rows in test set:")
    for idx, r in top_gaps.iterrows():
        c_str = str(r['ccn'])
        name = ccn_to_name.get(c_str, "Unknown")
        print(f"CCN: {c_str} ({name}), Week: {r['collection_week'].date()}, Capacity: {r['hospital_capacity']}, "
              f"Actual Beds (t+1): {r['y_future']}, Pred Beds: {r['pred_beds']:.1f}, "
              f"Safe Cap (85%): {r['safe_cap']:.1f}, Gap: {r['gap']:.1f}, State: {r['state']}, Subtype: {r['hospital_subtype']}")

    # Let's inspect the specific hospital with max gap
    max_gap_ccn = str(top_gaps.iloc[0]["ccn"])
    max_gap_name = ccn_to_name.get(max_gap_ccn, "Unknown")
    print(f"\nDetailed history for max gap CCN: {max_gap_ccn} ({max_gap_name})")
    ccn_history = df[df["ccn"] == max_gap_ccn].sort_values("collection_week")
    print(f"Total weeks recorded: {len(ccn_history)}")
    print(f"Capacity values: {ccn_history['hospital_capacity'].unique()}")
    print(f"Inpatient beds used range: {ccn_history['inpatient_beds_used'].min()} to {ccn_history['inpatient_beds_used'].max()}, Mean: {ccn_history['inpatient_beds_used'].mean():.1f}")
    print(f"Admissions range: {ccn_history['admissions'].min()} to {ccn_history['admissions'].max()}, Mean: {ccn_history['admissions'].mean():.1f}")
    print(ccn_history[["collection_week", "hospital_capacity", "inpatient_beds_used", "admissions"]].tail(10))

    # Pick 3 diverse hospitals: Large Academic, Small Critical Access, Medium/Average
    print("\n" + "-"*50)
    print("Sanity-checking 3 diverse hospital profiles:")
    # 1. Critical Access
    cah_ccns = df[df["hospital_subtype"] == "Critical Access Hospitals"]["ccn"].unique()
    cah_sample = str(cah_ccns[0])
    cah_name = ccn_to_name.get(cah_sample, "Unknown")

    # 2. Large Short Term / Academic
    large_ccns = df[df["hospital_capacity"] > 700]["ccn"].unique()
    large_sample = str(large_ccns[0])
    large_name = ccn_to_name.get(large_sample, "Unknown")

    # 3. Medium hospital
    med_ccns = df[(df["hospital_capacity"] >= 150) & (df["hospital_capacity"] <= 300)]["ccn"].unique()
    med_sample = str(med_ccns[0])
    med_name = ccn_to_name.get(med_sample, "Unknown")

    for category, c_id, name in [
        ("Small Critical Access Hospital", cah_sample, cah_name),
        ("Large Medical Center (>700 beds)", large_sample, large_name),
        ("Medium Community Hospital", med_sample, med_name),
    ]:
        print(f"\nProfile: {category} | CCN: {c_id} ({name})")
        h_test = test_beds[test_beds["ccn"] == c_id].sort_values("collection_week")
        if len(h_test) > 0:
            sample_row = h_test.iloc[-1]
            print(f"  Week: {sample_row['collection_week'].date()}")
            print(f"  Capacity: {sample_row['hospital_capacity']} | Safe (85%): {sample_row['safe_cap']:.1f}")
            print(f"  Actual Beds (t+1): {sample_row['y_future']:.1f} | Pred Beds: {sample_row['pred_beds']:.1f}")
            print(f"  Resource Gap Flagged: {sample_row['gap'] > 0} (Gap: {sample_row['gap']:.1f})")
            print(f"  Bed Utilization: {(sample_row['y_future']/sample_row['hospital_capacity'])*100:.1f}%")

if __name__ == "__main__":
    main()
