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


# ---------------------------------------------------------------------------
# Extended features (v2) — adds missingness signals, engineered ratios,
# and cohort-relative z-scores. See notebook 05 for derivation.
#
# Categorization story for new (anonymized) test tickers:
#   sector_code        - given in CSV
#   archetype          - assigned by ArchetypeClusterer from fundamentals
#   relative z-scores  - computed within each frame's own (group × year)
#                        cohort, using FEATURES only (no labels) -> safe to
#                        apply transductively to test
#   missingness flags  - derived from feature presence
# Every categorization is feature-derived, so it generalizes to strangers.
# ---------------------------------------------------------------------------

# Buckets used for per-category missingness counts. Splitting the total
# missing-count by economic meaning gives the model a richer signal than
# one global count: a row with 5 missing dividend fields is structurally
# different from one with 5 missing balance-sheet fields.
FEATURE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "valuation":   ("pe_ttm", "price_to_book", "price_to_sales", "growth_pe_ratio"),
    "profit":      ("gross_margin", "operating_margin", "net_margin", "roa", "roe", "rote"),
    "growth":      ("revenue_growth_3y", "revenue_growth_yoy"),
    "scale":       ("revenue_ttm", "net_income_ttm", "income_before_tax",
                    "eps_basic", "eps_diluted", "total_assets",
                    "stockholders_equity", "current_assets", "current_liabilities",
                    "long_term_debt", "goodwill", "inventory",
                    "shares_outstanding", "shares_diluted"),
    "leverage_liq":("current_ratio", "quick_ratio", "debt_to_equity"),
    "dividend":    ("dividend_yield", "dividends_ttm", "dividends_paid_ttm"),
}

# Features that get cohort-relative z-scores. Chosen because they are the
# textbook drivers of 1-year returns AND because their absolute level means
# different things across sectors / archetypes (a 30 P/E means something
# different for SaaS than for utilities).
RELATIVE_Z_FEATURES: tuple[str, ...] = (
    "pe_ttm",
    "price_to_book",
    "price_to_sales",
    "net_margin",
    "roe",
    "revenue_growth_yoy",
    "debt_to_equity",
    "dividend_yield",
)


def add_missingness_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add total + per-category missing counts and a pattern hash.

    `n_missing_total`            single int across all raw features
    `n_missing_<category>`       per-bucket counts (valuation, profit, ...)
    `missing_pattern_hash`       int32 hash of the high-NA-field NaN mask;
                                 same value = same disclosure profile
    """
    out = df.copy()
    raw_cols = [c for cols in FEATURE_CATEGORIES.values() for c in cols]
    raw_present = [c for c in raw_cols if c in out.columns]
    out["n_missing_total"] = out[raw_present].isna().sum(axis=1).astype("int16")
    for cat, cols in FEATURE_CATEGORIES.items():
        present = [c for c in cols if c in out.columns]
        if present:
            out[f"n_missing_{cat}"] = out[present].isna().sum(axis=1).astype("int8")

    pattern_cols = [c for c in MISSINGNESS_FLAG_COLS if c in out.columns]
    if pattern_cols:
        # Compact bitmask -> hash. Same mask -> same int, so trees can split
        # on "disclosure profile == 42" rather than chasing many flag combos.
        bits = out[pattern_cols].isna().astype(np.uint8).values
        weights = (1 << np.arange(len(pattern_cols), dtype=np.uint64))
        out["missing_pattern_hash"] = (bits @ weights).astype("int64") % 999983
    return out


def add_engineered_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Add 7 ratios derived from the raw fields.

    All operations are row-wise and use no group statistics, so the function
    is order-independent and can be applied to train, validation, and test
    without any fit step.
    """
    out = df.copy()

    # earnings_yield = 1 / PE, clipped to ±1 to neutralise tiny-denominator blowups
    pe = out.get("pe_ttm")
    if pe is not None:
        out["earnings_yield"] = np.where(
            pe.abs() > 1e-6, np.clip(1.0 / pe.replace(0, np.nan), -1.0, 1.0), np.nan
        )

    # growth acceleration: YoY relative to the 3y average
    if {"revenue_growth_yoy", "revenue_growth_3y"}.issubset(out.columns):
        out["accel_growth"] = out["revenue_growth_yoy"] - out["revenue_growth_3y"]

    # asset turnover: how much revenue per dollar of assets
    if {"revenue_ttm", "total_assets"}.issubset(out.columns):
        out["asset_turnover"] = out["revenue_ttm"] / out["total_assets"].replace(0, np.nan)

    # gross-to-op gap: high = SG&A / R&D burn between gross and operating line
    if {"gross_margin", "operating_margin"}.issubset(out.columns):
        out["gross_to_op_gap"] = out["gross_margin"] - out["operating_margin"]

    # quality composite: NaN-tolerant. We replace NaNs with the within-frame
    # median before z-scoring so missing components don't blank out the row.
    def _safe_z(series: pd.Series) -> pd.Series:
        filled = series.fillna(series.median())
        std = filled.std()
        return (filled - filled.mean()) / std if std > 0 else filled * 0.0

    quality_cols = ("net_margin", "roe", "current_ratio")
    if set(quality_cols).issubset(out.columns) and "debt_to_equity" in out.columns:
        score = sum(_safe_z(out[c]) for c in quality_cols)
        score = score - _safe_z(out["debt_to_equity"])
        out["quality_composite"] = score.astype(float)

    # distress flag: triple-condition binary signal for "operationally fragile"
    if {"net_margin", "current_ratio", "debt_to_equity"}.issubset(out.columns):
        out["distress_flag"] = (
            (out["net_margin"] < 0)
            & (out["current_ratio"] < 1)
            & (out["debt_to_equity"] > 2)
        ).fillna(False).astype("int8")

    # size proxy: log-scale composite of revenue and assets (sign-safe)
    if {"revenue_ttm", "total_assets"}.issubset(out.columns):
        out["size_proxy"] = 0.5 * (
            np.log1p(out["revenue_ttm"].clip(lower=0))
            + np.log1p(out["total_assets"].clip(lower=0))
        )
    return out


def add_relative_z_scores(
    df: pd.DataFrame,
    group_cols: list[str],
    features: Iterable[str] = RELATIVE_Z_FEATURES,
    suffix: str = "z",
) -> pd.DataFrame:
    """Add (feature - group_mean) / group_std for each (group_cols) cohort.

    Computed WITHIN the passed frame. For new tickers in the test cohort
    this means z-scoring against test's own (sector × 2024) distribution,
    which is leakage-free because z-scoring uses features only, never
    labels. Train and test each self-normalise within their own year(s);
    the model learns z-score effects that are stable across regimes.

    Small groups (n < 20) get the global mean/std as a fall-back instead
    of high-variance per-group estimates.
    """
    out = df.copy()
    for f in features:
        if f not in out.columns:
            continue
        g = out.groupby(group_cols, dropna=False)[f]
        group_size = g.transform("size")
        group_mean = g.transform("mean")
        group_std = g.transform("std")
        glob_mean = out[f].mean()
        glob_std = out[f].std()

        mean = np.where(group_size >= 20, group_mean, glob_mean)
        std = np.where(group_size >= 20, group_std, glob_std)
        std = np.where(std > 0, std, np.nan)

        out[f"{f}_{suffix}"] = (out[f] - mean) / std
    return out


def build_extended_features(
    frame: pd.DataFrame, archetype_col: str | None = "archetype"
) -> pd.DataFrame:
    """One-call pipeline: base features + missingness + ratios + z-scores.

    Order matters:
      1. add missingness counts (uses raw NaN mask, must run before any
         downstream imputation)
      2. add engineered ratios (depend on raw values)
      3. base build_features (drops non-feature cols, adds start_year etc.)
      4. relative z-scores by (sector × start_year), and by
         (archetype × start_year) if `archetype_col` is given and present.

    The caller is responsible for assigning `archetype` before calling
    this (typically via ArchetypeClusterer.predict). If `archetype` is not
    present, the archetype z-scores are simply skipped.
    """
    augmented = add_missingness_features(frame)
    augmented = add_engineered_ratios(augmented)

    # Carry the categorisation columns through so groupby can find them
    # after build_features drops the non-feature cols.
    carry = {"sector_code": augmented["sector_code"]}
    if archetype_col and archetype_col in augmented.columns:
        carry[archetype_col] = augmented[archetype_col]

    base = build_features(augmented)
    for k, v in carry.items():
        base[k] = v.values  # ensure aligned by position
    if "start_year" not in base.columns:
        base["start_year"] = augmented["start_year"].values

    base = add_relative_z_scores(
        base, group_cols=["sector_code", "start_year"], suffix="sect_yr_z"
    )
    if archetype_col and archetype_col in base.columns:
        base = add_relative_z_scores(
            base, group_cols=[archetype_col, "start_year"], suffix="arc_yr_z"
        )
    return base


def shrunk_archetype_means(
    train_archetypes: pd.Series, train_targets: pd.Series, prior: float = 200.0
) -> pd.Series:
    """Per-archetype mean, shrunk toward the global mean with `prior`
    pseudo-observations. Acts as a strong baseline AND a blend partner."""
    glob = train_targets.mean()
    stats = (
        pd.DataFrame({"a": train_archetypes.values, "y": train_targets.values})
        .groupby("a")["y"]
        .agg(["mean", "count"])
    )
    return (stats["mean"] * stats["count"] + glob * prior) / (stats["count"] + prior)
