// Mini presentation for the Aachen Investment Club: method walkthrough
// for the 1-year US-stock-return-from-fundamentals competition.
const path = require('path');
const PptxGenJS = require('pptxgenjs');

const pres = new PptxGenJS();
pres.layout = 'LAYOUT_WIDE'; // 13.33 x 7.5 inches
pres.title = 'Predicting 1-Year US Stock Returns from Fundamentals';
pres.company = 'Aachen Investment Club';

// Palette: Midnight Executive + a warm amber accent for risk/warning callouts.
const C = {
  navy:    '1E2761',
  navyLt:  '2E3D7F',
  ice:     'CADCFC',
  white:   'FFFFFF',
  grayBg:  'F4F6FB',
  text:    '202533',
  textMd:  '5A6275',
  accent:  'F2A516', // amber — used for warnings (gap, leakage)
  good:    '2C8A6D', // green for "model wins"
  bad:     'B23A3A', // red for "model loses"
};
const FH = 'Georgia';
const FB = 'Calibri';

function title(slide, text) {
  slide.addText(text, {
    x: 0.6, y: 0.45, w: 12.1, h: 0.7,
    fontFace: FH, fontSize: 32, bold: true, color: C.navy, valign: 'middle',
  });
}

function footer(slide, label) {
  slide.addText(label, {
    x: 0.6, y: 7.0, w: 12.1, h: 0.3,
    fontFace: FB, fontSize: 10, color: C.textMd, italic: true,
  });
}

// ---------------------------------------------------------------------------
// Slide 1 — Title
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addText('Predicting 1-Year US Stock Returns', {
    x: 0.8, y: 2.3, w: 11.7, h: 1.1,
    fontFace: FH, fontSize: 44, bold: true, color: C.white,
  });
  s.addText('from SEC-filing Fundamentals', {
    x: 0.8, y: 3.35, w: 11.7, h: 0.7,
    fontFace: FH, fontSize: 28, color: C.ice,
  });
  s.addShape(pres.ShapeType.line, {
    x: 0.85, y: 4.25, w: 1.2, h: 0,
    line: { color: C.accent, width: 3 },
  });
  s.addText('Method walkthrough · data prep, validation, first submission', {
    x: 0.8, y: 4.45, w: 11.7, h: 0.5,
    fontFace: FB, fontSize: 18, color: C.ice,
  });
  s.addText('Aachen Investment Club', {
    x: 0.8, y: 6.7, w: 8, h: 0.4,
    fontFace: FB, fontSize: 13, color: C.ice, italic: true,
  });
}

// ---------------------------------------------------------------------------
// Slide 2 — The Problem
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  title(s, 'The competition in one slide');

  // Left column — bullets
  s.addText(
    [
      { text: 'What we predict\n', options: { bold: true, color: C.navy, fontSize: 18 } },
      { text: 'For each company × quarter snapshot, the next 1-year stock return in percent.\n\n', options: { fontSize: 14, color: C.text } },
      { text: 'Data\n', options: { bold: true, color: C.navy, fontSize: 18 } },
      { text: '• Train: 2019-2022, 23,070 rows, real tickers (AAPL, NVDA, ...)\n', options: { fontSize: 14, color: C.text } },
      { text: '• Test: 2024, 8,520 rows, anonymised IDs (stock_0820, ...)\n', options: { fontSize: 14, color: C.text } },
      { text: '• 36 raw features: valuation, profitability, growth, balance sheet, dividends\n\n', options: { fontSize: 14, color: C.text } },
      { text: 'Metric\n', options: { bold: true, color: C.navy, fontSize: 18 } },
      { text: 'RMSE — punishes large misses quadratically.', options: { fontSize: 14, color: C.text } },
    ],
    { x: 0.6, y: 1.4, w: 7.4, h: 5.0, fontFace: FB, valign: 'top' }
  );

  // Right column — three stat callouts
  const stats = [
    { v: '23,070', l: 'train rows · 4 years' },
    { v: '8,520',  l: 'test rows · all 2024' },
    { v: 'cross-sectional', l: 'rank stocks at each date, not the market index' },
  ];
  stats.forEach((stat, i) => {
    const y = 1.55 + i * 1.55;
    s.addShape(pres.ShapeType.roundRect, {
      x: 8.4, y, w: 4.3, h: 1.3,
      fill: { color: C.grayBg }, line: { color: C.ice, width: 1 }, rectRadius: 0.08,
    });
    s.addText(stat.v, {
      x: 8.4, y: y + 0.1, w: 4.3, h: 0.7,
      fontFace: FH, fontSize: 32, bold: true, color: C.navy, align: 'center',
    });
    s.addText(stat.l, {
      x: 8.4, y: y + 0.78, w: 4.3, h: 0.45,
      fontFace: FB, fontSize: 12, color: C.textMd, align: 'center',
    });
  });

  footer(s, '01 / The problem');
}

// ---------------------------------------------------------------------------
// Slide 3 — The prediction-window gap (the central insight)
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  title(s, 'The prediction-window gap');

  s.addText('Every training row\'s forward return realises by 2023-12-31.\nThe test forward window runs 2024-2025 — entirely outside training-label coverage.', {
    x: 0.6, y: 1.25, w: 12.1, h: 0.9,
    fontFace: FB, fontSize: 15, color: C.text, italic: true,
  });

  // Timeline — years 2019..2026 spanning x ∈ [0.7, 12.6]  (w=11.9)
  const xStart = 0.8, yAxis = 4.1, axisW = 11.7, axisH = 0.12;
  const yearMin = 2019, yearMax = 2026;
  const yearSpan = yearMax - yearMin;
  const yearX = (y) => xStart + (y - yearMin) / yearSpan * axisW;

  // Train forward window bars (2019..2023)
  const trainColors = [C.navy, C.navyLt, '4A5BA0', '6A7BBA'];
  for (let i = 0; i < 4; i++) {
    const obsYear = 2019 + i;
    s.addShape(pres.ShapeType.rect, {
      x: yearX(obsYear), y: 2.9, w: yearX(obsYear + 1) - yearX(obsYear) - 0.04, h: 0.4,
      fill: { color: trainColors[i] }, line: { color: 'FFFFFF', width: 0.5 },
    });
    s.addText(`${obsYear} obs`, {
      x: yearX(obsYear), y: 2.5, w: yearX(obsYear + 1) - yearX(obsYear), h: 0.3,
      fontFace: FB, fontSize: 10, color: C.textMd, align: 'center',
    });
  }
  // Train forward coverage extends into 2023 (the 2022 obs's window ends 2023)
  s.addShape(pres.ShapeType.rect, {
    x: yearX(2023), y: 2.9, w: yearX(2024) - yearX(2023) - 0.04, h: 0.4,
    fill: { color: '8B9AD0', transparency: 30 }, line: { type: 'none' },
  });
  s.addText('train forward windows', {
    x: yearX(2019), y: 3.35, w: yearX(2024) - yearX(2019), h: 0.3,
    fontFace: FB, fontSize: 11, color: C.navy, align: 'center', bold: true,
  });

  // Test forward window
  s.addShape(pres.ShapeType.rect, {
    x: yearX(2024), y: 2.9, w: yearX(2026) - yearX(2024) - 0.04, h: 0.4,
    fill: { color: C.accent }, line: { color: 'FFFFFF', width: 0.5 },
  });
  s.addText('2024 obs · test forward window', {
    x: yearX(2024), y: 3.35, w: yearX(2026) - yearX(2024), h: 0.3,
    fontFace: FB, fontSize: 11, color: C.accent, align: 'center', bold: true,
  });

  // X-axis line + year ticks
  s.addShape(pres.ShapeType.line, {
    x: xStart, y: yAxis, w: axisW, h: 0, line: { color: C.textMd, width: 1 },
  });
  for (let y = yearMin; y <= yearMax; y++) {
    s.addShape(pres.ShapeType.line, {
      x: yearX(y), y: yAxis, w: 0, h: 0.08, line: { color: C.textMd, width: 1 },
    });
    s.addText(`${y}`, {
      x: yearX(y) - 0.3, y: yAxis + 0.08, w: 0.6, h: 0.3,
      fontFace: FB, fontSize: 10, color: C.textMd, align: 'center',
    });
  }

  // "Gap" annotation
  s.addText('NO training label here', {
    x: yearX(2024), y: 5.0, w: yearX(2026) - yearX(2024), h: 0.35,
    fontFace: FB, fontSize: 12, color: C.accent, italic: true, bold: true, align: 'center',
  });

  // Per-year return summary
  const yearStats = [
    { y: 2019, m: '+4%',   note: 'COVID crash + rebound' },
    { y: 2020, m: '+74%',  note: 'post-COVID melt-up' },
    { y: 2021, m: '-10%',  note: 'bear market' },
    { y: 2022, m: '+12%',  note: 'recovery' },
    { y: 2024, m: '?',     note: 'unseen regime' },
  ];
  const tableY = 5.7;
  const colW = 2.3;
  yearStats.forEach((st, i) => {
    const x = 0.85 + i * (colW + 0.05);
    const fill = st.y === 2024 ? C.accent : (i % 2 === 0 ? C.navy : C.navyLt);
    s.addShape(pres.ShapeType.roundRect, {
      x, y: tableY, w: colW, h: 1.0,
      fill: { color: fill }, line: { type: 'none' }, rectRadius: 0.05,
    });
    s.addText(`${st.y} mean: ${st.m}`, {
      x, y: tableY + 0.06, w: colW, h: 0.4,
      fontFace: FH, fontSize: 16, bold: true, color: C.white, align: 'center',
    });
    s.addText(st.note, {
      x, y: tableY + 0.5, w: colW, h: 0.45,
      fontFace: FB, fontSize: 11, color: C.white, align: 'center',
    });
  });

  footer(s, '02 / Core insight — train and test live in different return regimes');
}

// ---------------------------------------------------------------------------
// Slide 4 — Data Prep
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  title(s, 'Data prep — what we drop, what we add');

  // Drop column
  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 1.4, w: 5.9, h: 5.3,
    fill: { color: C.grayBg }, line: { color: C.ice, width: 1 }, rectRadius: 0.1,
  });
  s.addText('Drop', {
    x: 0.9, y: 1.55, w: 5.3, h: 0.5,
    fontFace: FH, fontSize: 22, bold: true, color: C.bad,
  });
  const drops = [
    ['period_start / period_end', 'Not in test.csv — using them in features crashes the test pipeline'],
    ['ticker', '100% anonymised in test, 0 overlap with train'],
    ['return_pct', 'The target — separated explicitly'],
  ];
  drops.forEach((d, i) => {
    const y = 2.2 + i * 1.45;
    s.addText('×', { x: 0.9, y, w: 0.4, h: 0.6, fontFace: FH, fontSize: 28, bold: true, color: C.bad });
    s.addText(d[0], { x: 1.4, y, w: 4.9, h: 0.4, fontFace: FB, fontSize: 15, bold: true, color: C.text });
    s.addText(d[1], { x: 1.4, y: y + 0.42, w: 4.9, h: 0.9, fontFace: FB, fontSize: 12, color: C.textMd });
  });

  // Add column
  s.addShape(pres.ShapeType.roundRect, {
    x: 6.85, y: 1.4, w: 5.9, h: 5.3,
    fill: { color: C.grayBg }, line: { color: C.ice, width: 1 }, rectRadius: 0.1,
  });
  s.addText('Add', {
    x: 7.15, y: 1.55, w: 5.3, h: 0.5,
    fontFace: FH, fontSize: 22, bold: true, color: C.good,
  });
  const adds = [
    ['start_year + years_since_2019', 'Only date field present in both train and test'],
    ['_is_missing flags (top 15 NA fields)', 'Test has 5-10pp higher missingness than train — flags are signal'],
    ['archetype (KMeans cluster, k=8)', 'Business profile, independent of sector_code (AMI = 0.075)'],
  ];
  adds.forEach((d, i) => {
    const y = 2.2 + i * 1.45;
    s.addText('+', { x: 7.15, y, w: 0.4, h: 0.6, fontFace: FH, fontSize: 28, bold: true, color: C.good });
    s.addText(d[0], { x: 7.65, y, w: 4.9, h: 0.4, fontFace: FB, fontSize: 15, bold: true, color: C.text });
    s.addText(d[1], { x: 7.65, y: y + 0.42, w: 4.9, h: 0.9, fontFace: FB, fontSize: 12, color: C.textMd });
  });

  footer(s, '03 / Data prep · all imputation, clipping, scaling fit on the train fold only');
}

// ---------------------------------------------------------------------------
// Slide 5 — Validation + ticker leakage
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  title(s, 'Validation — and the leakage we found');

  // Left: the split rationale
  s.addText(
    [
      { text: 'The 2022 holdout\n', options: { bold: true, color: C.navy, fontSize: 18 } },
      { text: 'Train on start_year < 2022, validate on start_year == 2022.\n', options: { fontSize: 13, color: C.text } },
      { text: 'Its forward window (2023) is the only stretch no earlier training row\'s label covers — the closest analog to the test situation.\n\n', options: { fontSize: 13, color: C.textMd, italic: true } },
      { text: 'Expanding-window diagnostic\n', options: { bold: true, color: C.navy, fontSize: 18 } },
      { text: '(19→20), (19-20→21), (19-21→22) — stability check.\n\n', options: { fontSize: 13, color: C.text } },
      { text: 'Target clipping\n', options: { bold: true, color: C.navy, fontSize: 18 } },
      { text: 'Train target clipped at 1st / 99th percentile of the train fold. Validation labels are never clipped.', options: { fontSize: 13, color: C.text } },
    ],
    { x: 0.6, y: 1.4, w: 6.4, h: 5.0, fontFace: FB, valign: 'top' }
  );

  // Right: the BIG callout
  s.addShape(pres.ShapeType.roundRect, {
    x: 7.4, y: 1.4, w: 5.3, h: 2.5,
    fill: { color: C.accent }, line: { type: 'none' }, rectRadius: 0.1,
  });
  s.addText('93.5%', {
    x: 7.4, y: 1.5, w: 5.3, h: 1.2,
    fontFace: FH, fontSize: 78, bold: true, color: C.white, align: 'center',
  });
  s.addText('of validation tickers also appear in training', {
    x: 7.4, y: 2.7, w: 5.3, h: 0.6,
    fontFace: FB, fontSize: 14, color: C.white, align: 'center',
  });
  s.addText('Test tickers are 100% strangers', {
    x: 7.4, y: 3.3, w: 5.3, h: 0.4,
    fontFace: FB, fontSize: 12, color: C.white, italic: true, align: 'center',
  });

  // The disparity numbers
  s.addText('Same fold, two RMSE numbers', {
    x: 7.4, y: 4.15, w: 5.3, h: 0.4,
    fontFace: FB, fontSize: 14, bold: true, color: C.navy,
  });
  const lines = [
    { label: 'tickers seen in train', val: '68.0', col: C.good },
    { label: 'novel tickers (test analog)', val: '77.3', col: C.bad },
    { label: 'overstatement', val: '+13%', col: C.accent },
  ];
  lines.forEach((ln, i) => {
    const y = 4.6 + i * 0.5;
    s.addText(ln.label, {
      x: 7.4, y, w: 3.6, h: 0.4,
      fontFace: FB, fontSize: 13, color: C.text,
    });
    s.addText(ln.val, {
      x: 11.0, y, w: 1.7, h: 0.4,
      fontFace: FH, fontSize: 18, bold: true, color: ln.col, align: 'right',
    });
  });

  footer(s, '04 / Validation · report overall RMSE AND novel-ticker RMSE');
}

// ---------------------------------------------------------------------------
// Slide 6 — Business archetypes
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  title(s, 'Business archetypes — 8 clusters that aren\'t sectors');

  s.addText('KMeans on size-invariant fundamentals (margins, ratios, growth, valuation, dividend yield). Adjusted Mutual Information vs sector_code = 0.075 — almost independent, so it adds new information.', {
    x: 0.6, y: 1.25, w: 12.1, h: 0.7,
    fontFace: FB, fontSize: 13, color: C.textMd, italic: true,
  });

  const rows = [
    ['#', 'Archetype',                       'Key fingerprint',                          'n',     'Mean ret', 'Std'],
    ['1', 'Mature dividend payer',           '6% NM, D/E 0.46, div yield 2.55%',        '4,865', '+14',      '96'],
    ['0', 'Cyclical loss-makers',            '-7% NM, declining YoY',                   '2,928', '+43',      '223'],
    ['5', 'Premium SaaS / software',         '54% GM, 32% OM, P/S 7',                   '2,775', '+6',       '44'],
    ['7', 'Capital-light compounders',       'ROE 24% / ROTE 33%, P/B 7.6',             '2,662', '+14',      '54'],
    ['2', 'GARP growers (no dividend)',      '23% 3y growth, yield 0',                  '2,610', '+21',      '148'],
    ['4', 'Leveraged mature',                'D/E 1.94 (highest), CR < 1',              '2,535', '+6',       '37'],
    ['6', 'Cheap hyper-growth',              '44% growth, P/S 0.9',                     '2,500', '+18',      '58'],
    ['3', 'Speculative biotech / early',     '68% GM but -29% OM, P/S 13',              '2,195', '+32',      '277'],
  ];

  const tableData = rows.map((r, i) => r.map((cell) => ({
    text: cell,
    options: i === 0
      ? { bold: true, color: C.white, fill: { color: C.navy }, fontSize: 12, align: 'center' }
      : { fontSize: 11, color: C.text, fill: { color: i % 2 === 0 ? C.grayBg : C.white } },
  })));

  s.addTable(tableData, {
    x: 0.6, y: 2.05, w: 12.1,
    colW: [0.5, 3.2, 4.3, 1.2, 1.3, 1.6],
    fontFace: FB,
    border: { type: 'solid', color: C.ice, pt: 0.5 },
    valign: 'middle', rowH: 0.45,
  });

  s.addText('Interpretation: regime-dependent winners. Premium SaaS underperformed in every train year; speculative biotech swings ±100pp.', {
    x: 0.6, y: 6.6, w: 12.1, h: 0.4,
    fontFace: FB, fontSize: 12, color: C.textMd, italic: true,
  });

  footer(s, '05 / Archetypes · use as a categorical feature + cluster-relative z-scores');
}

// ---------------------------------------------------------------------------
// Slide 7 — First model
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  title(s, 'First real model — robustness over flexibility');

  s.addText('The naive HGB baseline loses to dummy_mean on the 2022 fold (68.2 vs 64.9). The signal is fragile; the model has to be conservative. Three knobs:', {
    x: 0.6, y: 1.25, w: 12.1, h: 0.7,
    fontFace: FB, fontSize: 13, color: C.textMd, italic: true,
  });

  const cards = [
    {
      title: 'Huber loss (α=100)',
      body: 'Squared error inside ±100% returns; linear beyond. Stops a single +500% biotech row from dictating leaf splits.',
    },
    {
      title: 'Year-weighted samples',
      body: '2019 = 0.48, 2020 = 0.97, 2021 = 1.45. The training signal tilts toward the regime closest to the 2024 test cohort.',
    },
    {
      title: 'archetype as categorical',
      body: 'LightGBM puts each cluster in its own leaf without splitting on a continuous proxy. Native handling of cluster identity.',
    },
  ];
  cards.forEach((c, i) => {
    const x = 0.6 + i * 4.15;
    s.addShape(pres.ShapeType.roundRect, {
      x, y: 2.1, w: 3.95, h: 3.2,
      fill: { color: C.navy }, line: { type: 'none' }, rectRadius: 0.1,
    });
    s.addText(`${i + 1}`, {
      x: x + 0.3, y: 2.3, w: 0.6, h: 0.6,
      fontFace: FH, fontSize: 36, bold: true, color: C.accent, valign: 'middle',
    });
    s.addText(c.title, {
      x: x + 0.3, y: 2.9, w: 3.4, h: 0.6,
      fontFace: FH, fontSize: 17, bold: true, color: C.white,
    });
    s.addText(c.body, {
      x: x + 0.3, y: 3.55, w: 3.4, h: 1.6,
      fontFace: FB, fontSize: 12, color: C.ice,
    });
  });

  // Bottom result strip
  s.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 5.6, w: 12.1, h: 1.1,
    fill: { color: C.grayBg }, line: { color: C.ice, width: 1 }, rectRadius: 0.08,
  });
  const result = [
    { label: '2022 fold RMSE', value: '64.71', color: C.good },
    { label: 'vs dummy_mean', value: '−0.17', color: C.good },
    { label: 'best iteration', value: '2',     color: C.accent },
    { label: 'test pred std', value: '0.89',   color: C.accent },
  ];
  result.forEach((r, i) => {
    const x = 0.8 + i * 3.0;
    s.addText(r.value, {
      x, y: 5.7, w: 2.8, h: 0.55,
      fontFace: FH, fontSize: 26, bold: true, color: r.color, align: 'center',
    });
    s.addText(r.label, {
      x, y: 6.22, w: 2.8, h: 0.4,
      fontFace: FB, fontSize: 11, color: C.textMd, align: 'center',
    });
  });

  footer(s, '06 / Model · LightGBM with Huber, year weights, archetype categorical');
}

// ---------------------------------------------------------------------------
// Slide 8 — Results
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  title(s, 'Honest scorecard on the 2022 holdout');

  // Bar chart of overall RMSE
  const labels   = ['lgb huber + weights', 'archetype shrunk mean', 'archetype mean', 'dummy_mean (clipped)', 'dummy_median', 'HGB control (mse)'];
  const rmseAll  = [64.71, 64.77, 64.81, 64.88, 65.35, 68.22];

  s.addChart(pres.ChartType.bar, [
    { name: 'RMSE on 2022 fold', labels, values: rmseAll },
  ], {
    x: 0.6, y: 1.4, w: 7.3, h: 4.5,
    chartColors: [C.navy],
    barDir: 'bar',
    catAxisLabelFontSize: 11, catAxisLabelFontFace: FB, catAxisLabelColor: C.text,
    valAxisLabelFontSize: 10, valAxisLabelFontFace: FB, valAxisLabelColor: C.textMd,
    valAxisMinVal: 64.0, valAxisMaxVal: 69.0,
    showValue: true, dataLabelFontSize: 10, dataLabelFontFace: FB, dataLabelColor: C.navy,
    showLegend: false,
    showTitle: true, title: 'RMSE — lower is better', titleFontSize: 13, titleColor: C.navy, titleFontFace: FH,
  });

  // Right-side commentary
  s.addText('What the numbers actually say', {
    x: 8.1, y: 1.4, w: 4.6, h: 0.45,
    fontFace: FH, fontSize: 18, bold: true, color: C.navy,
  });
  s.addText(
    [
      { text: 'LightGBM wins by only 0.17 RMSE.\n', options: { bold: true, color: C.text, fontSize: 13 } },
      { text: 'Real improvement, but well within fold noise.\n\n', options: { color: C.textMd, fontSize: 12 } },
      { text: 'On novel tickers it is slightly worse.\n', options: { bold: true, color: C.bad, fontSize: 13 } },
      { text: '66.05 vs 65.65 for dummy_mean — the model finds firm-identity patterns that don\'t generalise.\n\n', options: { color: C.textMd, fontSize: 12 } },
      { text: '78% of squared error comes from 3 archetypes.\n', options: { bold: true, color: C.text, fontSize: 13 } },
      { text: 'Cyclical loss-makers (40%), premium SaaS (20%), mature dividend (18%). One model can\'t span them.', options: { color: C.textMd, fontSize: 12 } },
    ],
    { x: 8.1, y: 1.95, w: 4.6, h: 4.8, fontFace: FB, valign: 'top' }
  );

  footer(s, '07 / Results · submitted as lgb_huber_archetype_v1.csv');
}

// ---------------------------------------------------------------------------
// Slide 9 — Closing / what's next
// ---------------------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  s.addText('What\'s next', {
    x: 0.8, y: 0.7, w: 11.7, h: 0.8,
    fontFace: FH, fontSize: 34, bold: true, color: C.white,
  });
  s.addShape(pres.ShapeType.line, {
    x: 0.85, y: 1.55, w: 1.2, h: 0, line: { color: C.accent, width: 3 },
  });

  const ideas = [
    {
      n: '01', title: 'Within-date rank loss',
      body: 'LightGBM with LambdaRank, query = start_year. The competition rewards cross-sectional rank, not absolute return level. Pointwise MSE spends capacity on impossible level effects.',
    },
    {
      n: '02', title: 'Blend with archetype-shrunk mean',
      body: 'LGB and shrunk-mean err in opposite directions (LGB worse on novel tickers, shrunk mean worse on overlap). Averaging usually helps both fronts.',
    },
    {
      n: '03', title: 'Per-archetype models',
      body: 'Different α per cluster — biotech needs α≈200, leveraged-mature can use MSE. One global loss wastes 78% of the error budget on three sub-populations.',
    },
  ];
  ideas.forEach((idea, i) => {
    const y = 2.1 + i * 1.55;
    s.addShape(pres.ShapeType.roundRect, {
      x: 0.8, y, w: 11.7, h: 1.35,
      fill: { color: C.navyLt }, line: { color: C.accent, width: 0.5 }, rectRadius: 0.08,
    });
    s.addText(idea.n, {
      x: 1.0, y: y + 0.15, w: 1.4, h: 1.0,
      fontFace: FH, fontSize: 38, bold: true, color: C.accent, valign: 'middle',
    });
    s.addText(idea.title, {
      x: 2.4, y: y + 0.15, w: 9.8, h: 0.5,
      fontFace: FH, fontSize: 18, bold: true, color: C.white,
    });
    s.addText(idea.body, {
      x: 2.4, y: y + 0.62, w: 9.8, h: 0.7,
      fontFace: FB, fontSize: 12, color: C.ice,
    });
  });

  s.addText('Headline number to beat: 64.71 RMSE on the 2022 fold · 65.65 on novel tickers', {
    x: 0.8, y: 6.85, w: 11.7, h: 0.4,
    fontFace: FB, fontSize: 12, color: C.ice, italic: true, align: 'center',
  });
}

const outPath = path.join(__dirname, 'method_walkthrough.pptx');
pres.writeFile({ fileName: outPath }).then((p) => {
  console.log('wrote', p);
});
