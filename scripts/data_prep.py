"""Shared data-prep utilities for the stock-fundamentals competition.

Design constraints driven by the dataset (see notebook 00):

- The test set has no `period_start` / `period_end` / `return_pct` columns.
  The only date field available at inference time is `start_year`.
- Train tickers (AAPL, NVDA, ...) and test tickers (stock_0820, ...) do not
  overlap, so `ticker` must be dropped from features.
- The test prediction window (2024-2025) is entirely outside every training
  row's forward-return window (which ends 2023-12-31). Validation must
  therefore use a strict time split — the latest train year as holdout is
  the closest analog to the test situation.
- Target is fat-tailed (max +10571%); clip the training target only.
- Missingness is systematically higher in test, so missingness indicators
  on the highest-missingness fields are real signal.

Everything fit on data (imputers, clip cutoffs, target clipping) is fit on
the training fold only and applied to validation/test, to avoid leakage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import QuantileTransformer

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

# Columns dropped from the modeling feature matrix.
# - id: row identifier
# - ticker: real symbols in train, anonymized in test, zero overlap
# - period_start / period_end: not present in test; period_end is mechanically
#   tied to the forward-return window
# - return_pct: the target
NON_FEATURE_COLS: tuple[str, ...] = (
    "id",
    "ticker",
    "period_start",
    "period_end",
    "return_pct",
)

# Fields with the highest missingness in test (see notebook 00). Adding an
# explicit `<col>_is_missing` flag for these lets tree models split on
# "no data" rather than relying on an imputed median.
MISSINGNESS_FLAG_COLS: tuple[str, ...] = (
    "dividends_paid_ttm",
    "dividend_yield",
    "dividends_ttm",
    "gross_margin",
    "inventory",
    "debt_to_equity",
    "growth_pe_ratio",
    "long_term_debt",
    "shares_outstanding",
    "goodwill",
    "quick_ratio",
    "current_ratio",
    "revenue_growth_3y",
    "current_liabilities",
    "current_assets",
)


def load_raw(data_dir: Path | str = RAW_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load train.csv, test.csv, sample_submission.csv from `data_dir`.

    `period_start` / `period_end` are parsed as dates only when present
    (they are not in test.csv).
    """
    data_dir = Path(data_dir)
    train_path = data_dir / "train.csv"
    test_path = data_dir / "test.csv"
    sample_path = data_dir / "sample_submission.csv"

    train = pd.read_csv(train_path, parse_dates=["period_start", "period_end"])
    test = pd.read_csv(test_path)  # no date columns to parse
    sample_submission = pd.read_csv(sample_path)
    return train, test, sample_submission


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Turn a raw train or test frame into the modeling feature matrix.

    Same columns are produced for train and test so a single model fits both.
    `start_year` is kept (present in both); period_start/period_end/ticker
    are dropped. Missingness flags are added for the high-missingness fields.
    """
    out = frame.copy()

    # Year features. `start_year` exists in both train and test and equals
    # period_start.dt.year on every train row, so it is the safe substitute.
    out["years_since_2019"] = out["start_year"].astype("Int64") - 2019

    for col in MISSINGNESS_FLAG_COLS:
        if col in out.columns:
            out[f"{col}_is_missing"] = out[col].isna().astype("int8")

    drop_cols = [c for c in NON_FEATURE_COLS if c in out.columns]
    out = out.drop(columns=drop_cols)

    # Keep only numeric columns. sector_code is float in the raw files so it
    # passes through as a numeric category (fine for tree models). If we ever
    # add string columns, they should be encoded explicitly before this point.
    numeric = out.select_dtypes(include=[np.number, "Int64"]).columns.tolist()
    return out[numeric].astype(float)


@dataclass
class TimeSplit:
    """Indices and metadata for a single time-based validation split."""

    train_idx: np.ndarray
    valid_idx: np.ndarray
    valid_year: int
    description: str


def time_split(train: pd.DataFrame, valid_year: int = 2022) -> TimeSplit:
    """Split rows whose `start_year` < valid_year into train, others into valid.

    Default `valid_year=2022` gives the strongest analog to the test
    situation: the validation forward-return window (2023) lies outside
    every training row's forward window, mirroring how the 2024 test window
    lies outside every train+valid forward window.
    """
    train_mask = train["start_year"] < valid_year
    valid_mask = train["start_year"] == valid_year
    return TimeSplit(
        train_idx=np.where(train_mask)[0],
        valid_idx=np.where(valid_mask)[0],
        valid_year=valid_year,
        description=(
            f"train start_year<{valid_year} -> validate start_year=={valid_year}; "
            f"validation forward window ends {valid_year + 1}-12-31"
        ),
    )


def rolling_time_splits(
    train: pd.DataFrame, valid_years: Iterable[int] = (2020, 2021, 2022)
) -> list[TimeSplit]:
    """Expanding-window folds. Each fold trains on all earlier years."""
    return [time_split(train, year) for year in valid_years]


def clip_target_train_only(
    y_train: pd.Series, lower_pct: float = 1.0, upper_pct: float = 99.0
) -> tuple[pd.Series, float, float]:
    """Clip the *training* target at given percentiles.

    Returns the clipped series plus the (lo, hi) cutoffs so callers can log
    them. Validation and test targets are never clipped.
    """
    lo = float(np.percentile(y_train, lower_pct))
    hi = float(np.percentile(y_train, upper_pct))
    return y_train.clip(lo, hi), lo, hi


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root mean squared error — the competition metric."""
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


# ---------------------------------------------------------------------------
# Business-archetype clustering (see notebook 03 for derivation).
#
# Size-invariant fundamentals only — we want to cluster by *what kind of
# business* a row is, not by how big it is. With these features, k=8 KMeans
# produces interpretable groups (mature dividend payer, premium SaaS,
# speculative biotech, etc.) and is nearly independent of `sector_code`
# (AMI = 0.075), so the archetype carries new information.
# ---------------------------------------------------------------------------

ARCHETYPE_FEATURES: tuple[str, ...] = (
    "gross_margin",
    "operating_margin",
    "net_margin",
    "roa",
    "roe",
    "rote",
    "revenue_growth_3y",
    "revenue_growth_yoy",
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "pe_ttm",
    "price_to_book",
    "price_to_sales",
    "growth_pe_ratio",
    "dividend_yield",
)


@dataclass
class ArchetypeClusterer:
    """Fit-on-train, apply-to-anything KMeans pipeline for business archetypes.

    Use it like:
        clusterer = ArchetypeClusterer(k=8).fit(train_fold)
        train["archetype"] = clusterer.predict(train_fold)
        test["archetype"] = clusterer.predict(test)

    All preprocessing (median imputation, quantile-normal transform) is fit
    on the data passed to .fit, so when the validation fold is the
    "training" fold for a CV experiment, call .fit on that subset only —
    not on the full train DataFrame — to keep the pipeline leakage-safe.
    """

    k: int = 8
    random_state: int = 42
    _imputer: SimpleImputer | None = None
    _quantile: QuantileTransformer | None = None
    _kmeans: KMeans | None = None

    def fit(self, frame: pd.DataFrame) -> "ArchetypeClusterer":
        X = frame.loc[:, list(ARCHETYPE_FEATURES)]
        self._imputer = SimpleImputer(strategy="median")
        self._quantile = QuantileTransformer(
            output_distribution="normal",
            random_state=self.random_state,
            n_quantiles=min(2000, len(frame)),
            subsample=None,
        )
        Z = self._quantile.fit_transform(self._imputer.fit_transform(X))
        self._kmeans = KMeans(
            n_clusters=self.k, n_init=20, random_state=self.random_state
        ).fit(Z)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if self._kmeans is None:
            raise RuntimeError("ArchetypeClusterer must be fit before predict")
        X = frame.loc[:, list(ARCHETYPE_FEATURES)]
        Z = self._quantile.transform(self._imputer.transform(X))
        return self._kmeans.predict(Z)
