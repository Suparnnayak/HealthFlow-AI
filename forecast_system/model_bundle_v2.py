"""
Model Bundle V2

Stores the full set of retrained models for the V2 pipeline:
  - 2 targets (admissions, inpatient_beds_used)
  - 4 horizons (1-4 weeks)
  - 3 model types per (target, horizon): point, low-quantile, high-quantile

Total: 24 LightGBM boosters in one serialisable bundle.

The original ModelBundle (model_bundle.py) is NOT modified — old code
that loads the v1 bundle continues to work.
"""

import joblib
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Any


class ModelBundleV2:
    """
    V2 production model wrapper for dual-target, multi-horizon forecasting
    with prediction intervals.

    Layout
    ------
    self.models[target][horizon][model_type]
        target     : 'admissions' | 'inpatient_beds_used'
        horizon    : 1 | 2 | 3 | 4  (weeks ahead)
        model_type : 'point' | 'low' | 'high'

    Each value is a fitted ``lightgbm.LGBMRegressor``.
    """

    TARGETS = ("admissions", "inpatient_beds_used")
    HORIZONS = (1, 2, 3, 4)
    MODEL_TYPES = ("point", "low", "high")

    def __init__(
        self,
        models: Dict[str, Dict[int, Dict[str, Any]]],
        feature_columns: List[str],
        categorical_features: List[str],
        metadata: Optional[Dict] = None,
    ):
        """
        Parameters
        ----------
        models : nested dict  models[target][horizon][model_type] → LGBMRegressor
        feature_columns : ordered list of feature column names the models expect
        categorical_features : subset of feature_columns that are LightGBM categoricals
        metadata : arbitrary training metadata (dates, versions, dataset info, …)
        """
        self.models = models
        self.feature_columns = feature_columns
        self.categorical_features = categorical_features
        self.metadata = metadata or {}

        # Validate completeness
        for target in self.TARGETS:
            if target not in models:
                raise ValueError(f"Missing target '{target}' in models dict")
            for h in self.HORIZONS:
                if h not in models[target]:
                    raise ValueError(
                        f"Missing horizon {h} for target '{target}'"
                    )
                for mt in self.MODEL_TYPES:
                    if mt not in models[target][h]:
                        raise ValueError(
                            f"Missing model_type '{mt}' for "
                            f"target='{target}', horizon={h}"
                        )

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        target: str,
        horizon: int,
        X: pd.DataFrame,
        roll_mean_4: pd.Series,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict with residual-on-MA4 reconstruction.

        Parameters
        ----------
        target : 'admissions' or 'inpatient_beds_used'
        horizon : 1–4 (weeks ahead)
        X : DataFrame with self.feature_columns (feature values)
        roll_mean_4 : Series aligned with X containing the 4-week
                      trailing moving-average baseline

        Returns
        -------
        (point, low, high) : three np.ndarray of shape (len(X),)
            point = roll_mean_4 + point_model.predict(X)
            low   = roll_mean_4 + low_model.predict(X)
            high  = roll_mean_4 + high_model.predict(X)
            All clamped to >= 0.
        """
        if target not in self.TARGETS:
            raise ValueError(f"Unknown target '{target}'")
        if horizon not in self.HORIZONS:
            raise ValueError(f"Unknown horizon {horizon}")

        # Align features
        # LightGBM models store the exact features they were trained on
        point_mdl = self.models[target][horizon]["point"]
        target_features = point_mdl.feature_name_ if hasattr(point_mdl, "feature_name_") else self.feature_columns
        X_aligned = X[target_features].copy()
        # Fill numeric NaNs with 0 without touching pandas categorical columns
        num_cols = [c for c in target_features if c not in self.categorical_features]
        X_aligned[num_cols] = X_aligned[num_cols].fillna(0)

        base = roll_mean_4.values if hasattr(roll_mean_4, "values") else np.asarray(roll_mean_4)

        point_pred = base + self.models[target][horizon]["point"].predict(X_aligned)
        low_pred   = base + self.models[target][horizon]["low"].predict(X_aligned)
        high_pred  = base + self.models[target][horizon]["high"].predict(X_aligned)

        # Clamp to >= 0
        point_pred = np.maximum(point_pred, 0.0)
        low_pred   = np.maximum(low_pred, 0.0)
        high_pred  = np.maximum(high_pred, 0.0)

        # Ensure ordering: low <= point <= high
        low_pred  = np.minimum(low_pred, point_pred)
        high_pred = np.maximum(high_pred, point_pred)

        return point_pred, low_pred, high_pred

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Save ModelBundleV2 to disk via joblib."""
        joblib.dump(self, path)

    @staticmethod
    def load(path: str) -> "ModelBundleV2":
        """Load ModelBundleV2 from disk."""
        return joblib.load(path)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            "ModelBundleV2 Summary",
            "=" * 40,
            f"  Targets   : {list(self.TARGETS)}",
            f"  Horizons  : {list(self.HORIZONS)}",
            f"  Features  : {len(self.feature_columns)}",
            f"  Categoricals: {self.categorical_features}",
        ]
        total = 0
        for t in self.TARGETS:
            for h in self.HORIZONS:
                for mt in self.MODEL_TYPES:
                    total += 1
        lines.append(f"  Total models: {total}")
        if self.metadata:
            lines.append(f"  Metadata keys: {list(self.metadata.keys())}")
        return "\n".join(lines)
