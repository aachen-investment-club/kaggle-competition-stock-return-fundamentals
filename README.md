# Predict 1-Year US Stock Returns From Fundamentals

Starter repository for members of the Aachen Investment Club working on the Kaggle competition on 1-year forward stock return prediction from SEC-filing fundamentals.

## Competition In Plain English

You are given quarterly snapshots of US-listed companies and asked to predict the stock's **next 1-year return in percent**.

- Training observations start in **2019** and run through **2022**
- The forward return labels therefore extend through **2023-12-31**
- Test observations start in **2024-01-01**
- The score is **RMSE**, so large mistakes on extreme winners or losers are punished heavily

This is not a "forecast the whole market" problem. It is a **cross-sectional ranking and regression** problem:

- At each observation date, many stocks exist simultaneously
- The model tries to infer which stocks will outperform or underperform over the next year
- The signal is weak, noisy, regime-dependent, and contaminated by outliers

That makes this competition realistic. A good solution usually comes from:

1. Careful validation
2. Reasonable handling of missing values and outliers
3. Strong but robust tabular models
4. Disciplined feature engineering without leakage

## Why This Competition Is Hard

Fundamentals do contain information, but not in a simple linear way.

- Valuation can matter, but cheap stocks can stay cheap
- Profitability can matter, but high-quality names may already be priced richly
- Growth can matter, but only if expectations are not already too high
- Accounting metrics are noisy and sector-dependent
- The return target is fat-tailed, so a few names can dominate RMSE

You should assume that **small improvements in validation RMSE are meaningful** and that any large jump may indicate leakage or overfitting.

## Recommended Workflow

1. Understand the raw data before modeling
2. Build a leakage-safe time split
3. Establish simple baselines
4. Add model complexity only after validation is trustworthy
5. Keep a clean experiment log
6. Blend only models that independently add signal

## Repository Layout

```text
.
|-- README.md
|-- requirements.txt
|-- docs/
|   `-- competition_background.md
|-- data/
|   |-- raw/
|   |   `-- README.md
|   `-- processed/
|-- notebooks/
|   |-- 00_competition_intro_and_data_setup.ipynb
|   |-- 01_eda_and_validation_design.ipynb
|   `-- 02_baseline_models_and_submission.ipynb
`-- submissions/
```

## Getting Started

### 1. Create an environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Download the competition files

Option A: Kaggle API

```bash
kaggle competitions download -c predict-1-year-us-stock-returns-from-fundamentals -p data/raw
```

Option B: `kagglehub`

```python
import kagglehub

path = kagglehub.competition_download(
    "predict-1-year-us-stock-returns-from-fundamentals"
)
print(path)
```

Then place these files in `data/raw/`:

- `train.csv`
- `test.csv`
- `sample_submission.csv`

### 3. Work through the notebooks in order

- `00_competition_intro_and_data_setup.ipynb`: first-pass data load and sanity checks
- `01_eda_and_validation_design.ipynb`: missingness, outliers, sector effects, and split design
- `02_baseline_models_and_submission.ipynb`: first baseline models and a valid submission file

## Background Knowledge Members Should Have

Before building models, make sure everyone understands these concepts:

- **Cross-sectional prediction**: the target is stock-relative performance across many names, not one market index time series
- **Time leakage**: anything using future information, even indirectly, will destroy validation integrity
- **Regime dependence**: relationships that worked in 2020 may fail in 2022 or 2024
- **Outlier sensitivity**: RMSE rewards getting the center right, but punishes missing large movers
- **Sector comparability**: valuation and balance sheet ratios mean different things across sectors
- **Missingness as signal**: missing features are not always random in accounting data

The longer note in [docs/competition_background.md](/c:/Users/joni0/kaggle-competition-stock-return-fundamentals/docs/competition_background.md) goes into this in more detail.

## Initial Modeling Advice

Start with robust tabular methods before trying deep learning.

- Good first models: `DummyRegressor`, `Ridge`, `RandomForestRegressor`, `HistGradientBoostingRegressor`
- Strong next step: LightGBM or XGBoost with careful validation
- Useful preprocessing: date parsing, ratio sanity checks, optional winsorization, sector-aware diagnostics

For a first serious submission, a reasonable path is:

1. Exclude obvious identifiers like `ticker` from the first baseline
2. Use a 2022 holdout or expanding-window validation
3. Compare a mean/median baseline against a tree-based model
4. Inspect which stocks dominate your error

## Common Failure Modes

- Random train/test split across all rows
- Using statistics computed on the full dataset before splitting
- Treating the problem as classification without first understanding the regression target
- Blindly dropping rows with missing values
- Assuming ticker identity should always be included
- Tuning dozens of parameters against a weak validation split

## Suggested Team Setup

If multiple members collaborate, split the work:

- One person owns data auditing and validation design
- One person builds clean baseline models
- One person works on feature engineering
- One person tracks experiments and submissions

Shared standards matter more than fancy models.

## What To Try After The Baseline

- Winsorized or clipped training targets
- Log transforms for scale-heavy accounting variables
- Sector-relative features
- Interaction features between growth and valuation
- Per-date z-scoring of selected features
- Blending linear and tree models
- LightGBM with monotonicity experiments on selected ratios

## Operating Principle

Do not optimize for a clever story. Optimize for:

- leakage control
- stable validation
- reproducible notebooks
- incremental improvements

That is usually enough to beat a large fraction of Kaggle entrants in noisy finance competitions.
