# Competition Background

This note is for club members who know basic statistics and Python but have not yet worked on a cross-sectional equity prediction problem.

## 1. What The Target Really Is

`return_pct` is the **forward 1-year stock return in percent** for a given quarterly observation.

That means each training row is:

- a company
- at a specific quarter
- described only by information available at that time
- labeled with what happened over the following year

This is closer to an **equity cross-section problem** than a classic time-series forecasting problem.

## 2. Why Fundamentals Might Predict Returns

In public equities, fundamentals can matter through several channels:

- **Valuation**: cheaper companies may outperform if the market overreacted
- **Quality**: profitable, efficient firms may compound more reliably
- **Growth**: fast-growing firms can outperform if growth persistence is underpriced
- **Balance sheet strength**: leverage and liquidity affect resilience
- **Income distribution**: dividends can proxy maturity, discipline, or capital allocation style

None of these relationships are guaranteed. Markets are adaptive, and the same feature can change meaning across time and sectors.

## 3. Why This Is Difficult

### Low signal-to-noise ratio

Stock returns depend on many things not in the dataset:

- macro shocks
- rates
- sentiment
- market positioning
- earnings surprises after the snapshot date

Your model only sees stale accounting-style features and a few derived ratios.

### Fat tails

Some stocks will move far more than normal due to:

- distress
- short squeezes
- biotech binary events
- commodity shocks
- takeover rumors

Because the metric is RMSE, these observations can dominate your score.

### Non-stationarity

Relationships shift across years:

- 2020 behaved differently from 2022
- growth vs. value leadership changes over time
- rate regimes matter

Any validation scheme that ignores time will overstate quality.

## 4. Validation Matters More Than Model Choice

For this competition, a mediocre model with strong validation is more useful than a sophisticated model with leaky validation.

Recommended approaches:

### Simple holdout

- Train on rows with observation dates before **2022-01-01**
- Validate on rows with observation dates in **2022**

This is easy to explain and roughly mimics "train on past, predict nearer future".

### Expanding window

Example:

1. Train on 2019, validate on 2020
2. Train on 2019-2020, validate on 2021
3. Train on 2019-2021, validate on 2022

This gives multiple folds and shows whether performance is stable.

### What not to do

- random row splits
- target encoding fitted on the full dataset
- winsorization thresholds estimated on train+validation together
- scaling all years jointly before the split

## 5. Leakage Risks In This Dataset

Potential leakage is mostly operational rather than obvious.

### Date leakage

`period_start` and `period_end` are allowed inputs in the raw file, but treat them carefully:

- `period_start` can be converted into year and quarter features
- `period_end` is mechanically tied to the forward window and may not add useful signal

You should not build features that smuggle in future market information through outside joins unless explicitly allowed.

### Ticker leakage

Including `ticker` can help if some firms have persistent characteristics, but it also creates a strong overfitting risk if your validation is weak.

A sensible sequence is:

1. build a baseline without ticker
2. validate strongly
3. then test whether ticker encoding actually generalizes

### Global preprocessing leakage

Any transformation using global statistics should be fitted only on the training fold:

- imputation values
- standardization means and variances
- clipping cutoffs
- target encoders

## 6. Interpreting The Features

Most columns fall into one of these buckets:

- **Valuation**: `pe_ttm`, `price_to_book`, `price_to_sales`, `growth_pe_ratio`
- **Profitability**: margins, `roa`, `roe`, `rote`
- **Growth**: `revenue_growth_3y`, `revenue_growth_yoy`
- **Scale and size**: `market_cap`, `revenue_ttm`, assets, shares
- **Balance sheet strength**: liquidity and debt ratios
- **Dividends**: payout-related variables

Important caveats:

- some ratios explode when denominators are near zero
- some accounting quantities are highly skewed
- some sectors naturally sit at very different ratio levels

## 7. Feature Engineering Ideas

Good early ideas:

- parse dates into year and quarter
- log-transform large positive scale variables with `log1p`
- cap extreme ratio values
- create sector-relative z-scores
- create interactions such as profitability x valuation
- create flags for missingness on key fields

Be conservative. Finance datasets are especially good at producing fake signal from over-engineered features.

## 8. Model Ideas

### Strong starting point

- `HistGradientBoostingRegressor`
- `RandomForestRegressor`
- `Ridge`

These are easy to explain and hard to misuse relative to more advanced stacks.

### Stronger Kaggle-style options

- LightGBM
- XGBoost
- CatBoost

These often perform best on tabular data, but only after the validation design is credible.

### Blending

Blending works when models make different errors. For example:

- a linear model may capture broad valuation effects
- a tree model may capture non-linear interactions

Average them only if each model independently adds value.

## 9. How To Think About RMSE

RMSE punishes larger misses quadratically.

Implications:

- a few disastrous predictions can hurt more than many small improvements help
- stable, conservative models can outperform flashy unstable models
- robust training tricks such as clipping the training target may help

You should inspect the largest residuals in validation, not just the aggregate score.

## 10. Practical Research Questions For Members

These are good notebook-level projects:

- Are valuation features more predictive within sectors than globally?
- Does missingness itself carry information?
- Should we normalize features within each observation year?
- Does clipping the target improve validation RMSE?
- Are dividend variables useful after controlling for sector and size?
- Does adding ticker identity help or hurt on a true time split?

## 11. Minimum Standard For Any Submission

Before uploading anything to Kaggle, confirm:

1. validation uses time ordering
2. preprocessing is fit only on the training fold
3. notebook runs top-to-bottom
4. predictions match `sample_submission.csv` row count and ordering
5. the experiment is documented well enough that another club member can reproduce it

That is the standard this repository is designed to enforce.
