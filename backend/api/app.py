"""HTTP API for estimating daily net operating margin for a well."""

from contextlib import asynccontextmanager
import logging
import math
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field


LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
MODEL_ARTIFACT_PATH = BASE_DIR.parent / "artifacts" / "well_net_margin.joblib"
DATASET_PATH = BASE_DIR.parent / "dataset" / "well_data.csv"

FEATURE_COLUMNS = [
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
    "pressure_drawdown",
    "productivity_factor",
]
TARGET_COLUMN = "daily_net_margin_usd"


class WellData(BaseModel):
    """Observed well conditions and market values used by the trained model."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    permeability_md: float = Field(ge=0)
    porosity_fraction: float = Field(ge=0, le=1)
    well_depth_ft: float = Field(gt=0)
    tubing_diameter_in: float = Field(gt=0)
    choke_size_64th: float = Field(gt=0)
    reservoir_pressure_psi: float = Field(ge=0)
    reservoir_temp_f: float = Field(gt=-459.67)
    oil_gravity_api: float = Field(gt=0)
    gas_oil_ratio_scf_bbl: float = Field(ge=0)
    bottomhole_pressure_psi: float = Field(ge=0)
    wellhead_pressure_psi: float = Field(ge=0)
    water_cut_fraction: float = Field(ge=0, le=1)
    oil_price_usd_bbl: float = Field(ge=0)
    gas_price_usd_mcf: float = Field(ge=0)


class PredictionResponse(BaseModel):
    estimated_daily_net_margin_usd: float
    target: str
    model: str
    interpretation: str


class MarginBand(BaseModel):
    label: str
    count: int
    percentage: float


class RevenueComponent(BaseModel):
    label: str
    average_usd_per_well_day: float


class TopWell(BaseModel):
    well_id: str
    daily_net_margin_usd: float


class DashboardSummary(BaseModel):
    well_count: int
    positive_margin_count: int
    negative_margin_count: int
    positive_margin_percentage: float
    average_daily_net_margin_usd: float
    median_daily_net_margin_usd: float
    margin_distribution: list[MarginBand]
    revenue_components: list[RevenueComponent]
    top_wells: list[TopWell]
    time_series_available: bool


def _load_model_artifact() -> dict[str, Any]:
    if not MODEL_ARTIFACT_PATH.is_file():
        raise RuntimeError(f"Model artifact not found: {MODEL_ARTIFACT_PATH}")

    artifact = joblib.load(MODEL_ARTIFACT_PATH)
    if not isinstance(artifact, dict):
        raise RuntimeError("Model artifact has an invalid format.")

    model = artifact.get("model")
    if model is None:
        raise RuntimeError("Model artifact does not contain a trained model.")
    if artifact.get("feature_columns") != FEATURE_COLUMNS:
        raise RuntimeError(
            "The API feature schema does not match the saved model artifact."
        )
    if artifact.get("target_column") != TARGET_COLUMN:
        raise RuntimeError("The model artifact has an unexpected prediction target.")
    if getattr(model, "n_features_in_", None) != len(FEATURE_COLUMNS):
        raise RuntimeError("The model feature count does not match the API schema.")

    return artifact


def _load_dashboard_summary() -> DashboardSummary:
    if not DATASET_PATH.is_file():
        raise RuntimeError(f"Dashboard dataset not found: {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH)
    required_columns = {
        "well_id",
        "oil_rate_bbl_day",
        "gas_rate_scf_day",
        "oil_price_usd_bbl",
        "gas_price_usd_mcf",
        "daily_opex_usd",
        "daily_revenue_usd",
    }
    missing_columns = sorted(required_columns - set(df.columns))
    if df.empty or missing_columns:
        raise RuntimeError(
            f"Dashboard dataset is empty or missing columns: {missing_columns}"
        )

    oil_revenue = df["oil_rate_bbl_day"] * df["oil_price_usd_bbl"]
    gas_revenue = (
        df["gas_rate_scf_day"] / 1000
    ) * df["gas_price_usd_mcf"]
    net_margin = oil_revenue + gas_revenue - df["daily_opex_usd"]

    numeric_values = np.column_stack(
        [
            oil_revenue.to_numpy(dtype=float),
            gas_revenue.to_numpy(dtype=float),
            df["daily_opex_usd"].to_numpy(dtype=float),
            df["daily_revenue_usd"].to_numpy(dtype=float),
            net_margin.to_numpy(dtype=float),
        ]
    )
    if not np.isfinite(numeric_values).all():
        raise RuntimeError("Dashboard dataset contains non-finite numeric values.")
    if not np.allclose(
        df["daily_revenue_usd"].to_numpy(dtype=float),
        net_margin.to_numpy(dtype=float),
        rtol=1e-6,
        atol=1e-4,
    ):
        raise RuntimeError(
            "The dataset's daily_revenue_usd values do not match the "
            "calculated net margin."
        )

    well_count = len(df)
    bands = [
        ("< 0", net_margin < 0),
        ("0–100", (net_margin >= 0) & (net_margin < 100)),
        ("100–250", (net_margin >= 100) & (net_margin < 250)),
        ("250–500", (net_margin >= 250) & (net_margin < 500)),
        ("≥ 500", net_margin >= 500),
    ]
    margin_distribution = [
        MarginBand(
            label=label,
            count=int(mask.sum()),
            percentage=round(float(mask.mean() * 100), 2),
        )
        for label, mask in bands
    ]

    top_rows = (
        df.assign(daily_net_margin_usd=net_margin)
        .nlargest(5, "daily_net_margin_usd")
        .loc[:, ["well_id", "daily_net_margin_usd"]]
    )
    top_wells = [
        TopWell(
            well_id=str(row.well_id),
            daily_net_margin_usd=round(float(row.daily_net_margin_usd), 2),
        )
        for row in top_rows.itertuples(index=False)
    ]

    return DashboardSummary(
        well_count=well_count,
        positive_margin_count=int((net_margin > 0).sum()),
        negative_margin_count=int((net_margin < 0).sum()),
        positive_margin_percentage=round(
            float((net_margin > 0).mean() * 100), 2
        ),
        average_daily_net_margin_usd=round(float(net_margin.mean()), 2),
        median_daily_net_margin_usd=round(float(net_margin.median()), 2),
        margin_distribution=margin_distribution,
        revenue_components=[
            RevenueComponent(
                label="Receita de petróleo",
                average_usd_per_well_day=round(float(oil_revenue.mean()), 2),
            ),
            RevenueComponent(
                label="Receita de gás",
                average_usd_per_well_day=round(float(gas_revenue.mean()), 2),
            ),
            RevenueComponent(
                label="OPEX",
                average_usd_per_well_day=round(
                    float(df["daily_opex_usd"].mean()), 2
                ),
            ),
        ],
        top_wells=top_wells,
        time_series_available=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    artifact = _load_model_artifact()
    app.state.model_artifact = artifact
    app.state.model = artifact["model"]
    app.state.dashboard_summary = _load_dashboard_summary()
    yield


app = FastAPI(
    title="PetroAI Well Margin API",
    description=(
        "Estimates daily net operating margin under observed well conditions. "
        "It does not recommend operating setpoint changes."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
if "*" in allowed_origins:
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS must list explicit origins; '*' is not allowed."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def home() -> dict[str, str]:
    return {
        "service": "PetroAI Well Margin API",
        "status": "ready",
        "docs": "/docs",
        "prediction_endpoint": "/predict",
    }


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    """Report readiness after the model has been loaded successfully."""
    if not hasattr(request.app.state, "model"):
        raise HTTPException(status_code=503, detail="Model is not ready.")
    return {"status": "ok"}


@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(request: Request) -> DashboardSummary:
    """Return cached aggregates calculated from the well dataset."""
    if not hasattr(request.app.state, "dashboard_summary"):
        raise HTTPException(
            status_code=503,
            detail="Dashboard data is not ready.",
        )
    return request.app.state.dashboard_summary


@app.post("/predict", response_model=PredictionResponse)
def predict(data: WellData, request: Request) -> PredictionResponse:
    """Estimate daily net margin; this is not an operational recommendation."""
    values = data.model_dump()
    values["pressure_drawdown"] = (
        data.reservoir_pressure_psi - data.bottomhole_pressure_psi
    )
    values["productivity_factor"] = (
        data.permeability_md * data.porosity_fraction
    )
    input_data = pd.DataFrame(
        [[values[column] for column in FEATURE_COLUMNS]],
        columns=FEATURE_COLUMNS,
    )

    prediction_value = float(request.app.state.model.predict(input_data)[0])
    if not math.isfinite(prediction_value):
        LOGGER.error("Model returned a non-finite daily net margin prediction.")
        raise HTTPException(
            status_code=500,
            detail="The model could not produce a valid prediction.",
        )

    artifact = request.app.state.model_artifact
    selected_model = artifact.get("evaluation", {}).get(
        "selected_model", "unknown"
    )
    return PredictionResponse(
        estimated_daily_net_margin_usd=prediction_value,
        target=TARGET_COLUMN,
        model=selected_model,
        interpretation=(
            "Estimate for observed conditions only; not a recommendation to "
            "change well operating settings."
        ),
    )
