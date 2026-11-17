"""Screen wells by estimated daily net operating margin.

The CSV's daily_revenue_usd values match net margin, not gross revenue. Gross
sales are derived from production rates and prices. This is a screening model
under observed conditions, not a causal model for new operating setpoints.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BACKEND_DIR / "dataset" / "well_data.csv"
MODEL_PATH = BACKEND_DIR / "artifacts" / "well_net_margin.joblib"

REPORTED_MARGIN_COLUMN = "daily_revenue_usd"
OPEX_COLUMN = "daily_opex_usd"
TARGET_COLUMN = "daily_net_margin_usd"
TARGET_DEFINITION = (
    "oil_rate_bbl_day * oil_price_usd_bbl + "
    "(gas_rate_scf_day / 1000) * gas_price_usd_mcf - daily_opex_usd"
)

SOURCE_FEATURES = [
    "permeability_md",
    "porosity_fraction",
    "well_depth_ft",
    "tubing_diameter_in",
    "choke_size_64th",
    "reservoir_pressure_psi",
    "reservoir_temp_f",
    "oil_gravity_api",
    "gas_oil_ratio_scf_bbl",
    "bottomhole_pressure_psi",
    "wellhead_pressure_psi",
    "water_cut_fraction",
    "oil_price_usd_bbl",
    "gas_price_usd_mcf",
]
FEATURE_COLUMNS = SOURCE_FEATURES + ["pressure_drawdown", "productivity_factor"]
REVENUE_CALCULATION_COLUMNS = [
    "oil_rate_bbl_day",
    "gas_rate_scf_day",
    "oil_price_usd_bbl",
    "gas_price_usd_mcf",
    OPEX_COLUMN,
]
REQUIRED_COLUMNS = list(
    dict.fromkeys(
        SOURCE_FEATURES
        + REVENUE_CALCULATION_COLUMNS
        + [REPORTED_MARGIN_COLUMN]
    )
)


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load well observations from a project-relative CSV path."""
    data_path = Path(path)
    if not data_path.is_file():
        raise FileNotFoundError(f"Dataset not found: {data_path}")
    return pd.read_csv(data_path)


def explore_data(df: pd.DataFrame) -> dict:
    """Return a compact data-quality and business-target summary."""
    summary = {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
    }

    if set(REQUIRED_COLUMNS).issubset(df.columns):
        gross_revenue = (
            df["oil_rate_bbl_day"] * df["oil_price_usd_bbl"]
            + (df["gas_rate_scf_day"] / 1000) * df["gas_price_usd_mcf"]
        )
        margin = gross_revenue - df[OPEX_COLUMN]
        negative_margin = margin < 0
        summary["negative_net_margin_rows"] = int(negative_margin.sum())
        if "well_id" in df.columns:
            summary["negative_net_margin_well_ids"] = (
                df.loc[negative_margin, "well_id"].tolist()
            )
        summary["reported_margin_formula_mae_usd_per_day"] = float(
            (df[REPORTED_MARGIN_COLUMN] - margin).abs().mean()
        )
        summary["net_margin_summary_usd_per_day"] = (
            margin.describe().round(2).to_dict()
        )

    return summary


def prepare_model(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Build features and formula-based daily net margin."""
    if df.empty:
        raise ValueError("The dataset is empty.")

    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")

    non_numeric_columns = [
        column
        for column in REQUIRED_COLUMNS
        if not pd.api.types.is_numeric_dtype(df[column])
    ]
    if non_numeric_columns:
        raise TypeError(f"Expected numeric columns: {non_numeric_columns}")

    numeric_data = df[REQUIRED_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(numeric_data).all():
        raise ValueError("Required modeling columns contain NaN or infinite values.")

    nonnegative_columns = [
        "oil_rate_bbl_day",
        "gas_rate_scf_day",
        "oil_price_usd_bbl",
        "gas_price_usd_mcf",
        OPEX_COLUMN,
    ]
    negative_values = {
        column: int((df[column] < 0).sum())
        for column in nonnegative_columns
        if (df[column] < 0).any()
    }
    if negative_values:
        raise ValueError(
            f"Production rates, prices, and operating costs must be nonnegative: "
            f"{negative_values}"
        )

    gross_revenue = (
        df["oil_rate_bbl_day"] * df["oil_price_usd_bbl"]
        + (df["gas_rate_scf_day"] / 1000) * df["gas_price_usd_mcf"]
    )
    net_margin = gross_revenue - df[OPEX_COLUMN]
    reported_margin = df[REPORTED_MARGIN_COLUMN]
    mismatches = ~np.isclose(
        reported_margin.to_numpy(dtype=float),
        net_margin.to_numpy(dtype=float),
        rtol=1e-6,
        atol=1e-4,
    )
    if mismatches.any():
        bad_ids = (
            df.loc[mismatches, "well_id"].tolist()
            if "well_id" in df.columns
            else df.index[mismatches].tolist()
        )
        raise ValueError(
            "The calculated net margin does not match the CSV's "
            f"{REPORTED_MARGIN_COLUMN} values for rows/wells: {bad_ids}"
        )

    prepared = df.copy()
    prepared["pressure_drawdown"] = (
        prepared["reservoir_pressure_psi"] - prepared["bottomhole_pressure_psi"]
    )
    prepared["productivity_factor"] = (
        prepared["permeability_md"] * prepared["porosity_fraction"]
    )
    prepared[TARGET_COLUMN] = net_margin

    X = prepared[FEATURE_COLUMNS].copy()
    y = prepared[TARGET_COLUMN].copy()
    return X, y


def _regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict:
    return {
        "mae_usd_per_day": float(mean_absolute_error(y_true, y_pred)),
        "rmse_usd_per_day": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


def train_model(
    X: pd.DataFrame, y: pd.Series
) -> tuple[object, dict]:
    """Select by cross-validated MAE, report holdout metrics, then refit."""
    if len(X) < 10:
        raise ValueError("At least 10 well records are required for this evaluation.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    candidates = {
        "linear_regression": make_pipeline(StandardScaler(), LinearRegression()),
        "random_forest": RandomForestRegressor(
            n_estimators=300,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=2,
            random_state=42,
        ),
    }

    model_results = {}
    for name, candidate in candidates.items():
        cv_mae = -cross_val_score(
            candidate,
            X_train,
            y_train,
            cv=cv,
            scoring="neg_mean_absolute_error",
        ).mean()
        fitted = clone(candidate).fit(X_train, y_train)
        model_results[name] = {
            "cv_mae_usd_per_day": float(cv_mae),
            "holdout": _regression_metrics(y_test, fitted.predict(X_test)),
        }

    baseline = DummyRegressor(strategy="mean").fit(X_train, y_train)
    baseline_metrics = _regression_metrics(y_test, baseline.predict(X_test))

    selected_name = min(
        model_results,
        key=lambda name: model_results[name]["cv_mae_usd_per_day"],
    )
    final_model = clone(candidates[selected_name]).fit(X, y)

    report = {
        "selected_model": selected_name,
        "selection_metric": "5-fold cross-validated MAE",
        "models": model_results,
        "mean_baseline_holdout": baseline_metrics,
        "holdout_fraction": 0.2,
        "random_state": 42,
    }
    return final_model, report


def save_model(model: object, report: dict, path: Path = MODEL_PATH) -> Path:
    """Persist the estimator together with its input and target contract."""
    model_path = Path(path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "target_definition": TARGET_DEFINITION,
            "business_objective": (
                "Screen wells by estimated daily net operating margin; "
                "prioritize engineering review, not automatic setpoint changes."
            ),
            "evaluation": report,
        },
        model_path,
    )
    return model_path


def main() -> None:
    df = load_data()
    data_summary = explore_data(df)
    print(f"Dataset summary: {data_summary}")

    X, y = prepare_model(df)
    model, report = train_model(X, y)
    model_path = save_model(model, report)

    print(f"Evaluation: {report}")
    print(f"Saved model artifact: {model_path}")


if __name__ == "__main__":
    main()
