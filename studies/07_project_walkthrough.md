# Project Walkthrough — How Everything Connects

This document traces the complete flow from a PDF file arriving in `data/reports/` to a chart appearing on your phone.

## Phase 1: Parsing (`uv run python main.py`)

### 1.1 Discovery

```
main.py
  → scans data/reports/*.pdf
  → checks data/parsed/ for existing YYYY-MM.json
  → skips already-parsed months
```

### 1.2 Layout detection

```
parser.py: parse_pdf()
  → opens PDF with pdfplumber
  → _detect_layout(pages):
      → reads page 2 (index 1) text
      → if "Resumo da Carteira" found → returns "new"
      → otherwise → returns "old"
  → if "new": _parse_summary_page(pages[1]) + _parse_movements_page(pages[2])
  → if "old": find page with "Principais números", use _parse_old_summary_page()
```

**Why this matters:** AUVP changed their report format around Nov 2025. The two formats have completely different page structures, different table layouts, and different data availability. The parser must detect which format it's dealing with before choosing the right extraction strategy. This detection is fragile — if AUVP changes the "Resumo da Carteira" heading, the parser would misclassify new-format PDFs as old.

| | New format (Nov 2025+) | Old format (before) |
|---|---|---|
| Pages | ~10 | ~8 |
| Summary | Page 2: vertical layout with separate metric blocks | Page 3: horizontal table ("Patrimônio inicial \| Movimentações \| ...") |
| Portfolio | Page 2: single-column table | Page 3: horizontal table |
| Fixed income | Separate rows per indexer | All indexers in one merged cell with `\n` |
| Stocks/FIIs | Dedicated pages with extractable tables | Chart images only (no table data) |
| Proventos | Chart image with labeled legend | Chart image, sometimes without per-category labels |
| Allocation | Chart images (donut charts) | Chart images |

### 1.3 Summary extraction

**New format** (`_parse_summary_page`):
```
Page text: "R$ 1.243.581,34\n...4,40% R$ 45.280,50\n...R$ 36.560,34 -R$ 4.316,47"
  → regex extracts patrimony, return%, gains, applications, movements
  → regex extracts portfolio lines: "Renda Fixa R$ 684.236,06"
  → calculates allocation percentages from values
```

**Old format** (`_parse_old_summary_page`):
```
Table 0: ['Patrimônio inicial', 'Movimentações', 'Patrimônio final', 'Rentabilidade %', 'Rendimentos']
         ['R$ 874.707,57',     'R$ 10.497,50',  'R$ 902.824,81',    '2,00%',          'R$ 17.619,74']
  → reads column headers, maps to fields by header name
Table 1: ['Renda Fixa', 'Ações', 'FIIs', 'Internacional', 'COE']
         ['R$ 630.523,31', ...]
  → horizontal portfolio table
```

### 1.4 Proventos extraction

```
_parse_movements_page()
  → extracts full page text
  → finds "Proventos:" in text, takes everything after it
  → checks: does the text after "Proventos:" contain any "R$"?
      (uses: "R$" not in prov_text.replace("Proventos:", ""))
      (the .replace() avoids matching "R$" that might be in the heading itself)
  → if NO R$ values in text → chart is an image, fall back to OCR:
      → _ocr_proventos_chart(page)
        → scans page.images for largest image with top > 300 and width > 200
        → crops the page to that image's bounding box
        → converts to PIL image at 400 DPI
        → grayscale + sharpen
        → pytesseract.image_to_string()
        → returns OCR text like "@ Acdes: R$ 1.982,54 @ Fils: R$ 744,11 ..."
  → regex matches ações, FIIs, cupons (with OCR-tolerant patterns)
  → total = sum of the three (not extracted separately — OCR total line is ambiguous)
```

**Why `top > 300`?** The proventos chart position varies between formats: new format at `top=413`, old format as low as `top=350`. We use 300 as a safe threshold that catches both while avoiding the header logo image (typically at `top < 50`).

### 1.5 Fixed income, stocks, FIIs

```
_find_page_by_title("Indexadores de Ativos de Renda Fixa")
  → or fallback: _find_page_by_title("Indexador")
  → _parse_fixed_income_page(): handles both row-per-indexer and merged-cell formats

Stocks/FIIs: scans ALL pages for tables with "ATIVO" + "QUANTIDADE" headers
  → determines type by page context ("Ações" vs "Fundos Imobili")
  → or by ticker suffix (11/12 = FII)
  → _clean_ticker() fixes spaces: "AL  P11" → "ALUP11"
```

### 1.6 Serialization

```
MonthlyReport dataclass
  → .to_dict() (uses dataclasses.asdict)
  → .to_json() (json.dumps with indent=2)
  → written to data/parsed/2026-01.json
```

## Phase 2: Dashboard (`uv run streamlit run app.py`)

### 2.1 Startup

```
app.py loads
  → st.set_page_config() — must be first
  → check_auth() — if APP_PASSWORD set, shows login form and st.stop()
  → get_reports() — loads all JSON files, cached for 10 seconds
```

### 2.2 Main page render

```
User selects month in sidebar
  → report = months[selected_month]

Resumo section:
  → 4 metrics in 2x2 grid

Evolução do Patrimônio:
  → period selector (De/Até)
  → filters reports to range
  → builds DataFrame with patrimony + cumulative aportes
  → Plotly line chart (patrimony + aportes lines)
  → aportes bar chart with dual Y-axis

Rentabilidade:
  → bar chart (monthly) + line chart (cumulative)
  → cumulative = compound: (1+r1) * (1+r2) * ... - 1

Proventos:
  → stacked bar (ações/FIIs/cupons) + total line
  → evolution table
```

### 2.3 Detail page render

```
pages/detalhes.py
  → independent script, runs top-to-bottom
  → own check_auth() call
  → own month selector
  → allocation pie, fixed income table+pie, stocks table, FIIs table
```

### 2.4 Contributions (aportes) flow

```
User opens sidebar → "Registrar Aporte (BTG)" expander
  → selects month, enters value
  → clicks "Salvar"
  → save_contributions() writes to data/contributions.json
  → st.rerun() refreshes the page
  → patrimony chart recalculates with new aporte
```

## Data model summary

Fields with `= field(default_factory=list)` or `= None` may be empty/missing, especially in old-format reports where stocks, FIIs, and sectors are chart images with no extractable data.

```
MonthlyReport
├── date: "2026-01-31"
├── patrimony: 1243581.34
├── monthly_return_pct: 4.4
├── monthly_gains: 45280.50
├── applications: 36560.34
├── movements: -4316.47
├── portfolio: [PortfolioAllocation, ...]
│   └── asset_class, value, percentage
├── target_allocation: [TargetAllocation, ...]
├── fixed_income: [FixedIncomeAsset, ...]
│   └── indexer, avg_rate, value, percentage
├── stocks: [Stock, ...]
│   └── ticker, quantity, value, percentage
├── fiis: [FII, ...]
│   └── ticker, quantity, value, percentage
├── sector_distribution: [SectorDistribution, ...]
├── fii_segments: [FIISegment, ...]
├── proventos: Proventos
│   └── acoes, fiis, cupons_rf, total
└── acquired_assets: [Movement, ...]
    └── asset_class, value
```

## Contributions (aportes) flow

This is a separate data path from the PDF parsing:

```
User opens sidebar → "Registrar Aporte (BTG)" expander
  → selects month from dropdown (all months from 2025-07 to latest)
  → enters value in number_input
  → clicks "Salvar"
  → save_contributions() writes dict to data/contributions.json
  → st.rerun() triggers full script re-run
  → load_contributions() reads fresh data from disk (NOT cached)
  → patrimony chart recalculates cumulative aportes
  → aportes chart rebuilds with new bar
```

**Key detail:** `load_contributions()` is NOT cached (unlike `get_reports()`). This is intentional — aportes change during a session, so we always read fresh from disk. Reports change only when you re-run `main.py`, so caching them is safe.

## Allocation percentage calculation

The PDF's portfolio table gives values but not always percentages. The parser computes them:

```python
# From _parse_summary_page():
total = sum(p.value for p in portfolio)   # sum all asset class values
for p in portfolio:
    p.percentage = round(p.value / total * 100, 2)
```

This means allocation percentages in our data are derived from values, not extracted from the PDF. The PDF may show slightly different percentages (due to rounding) but our computed values are accurate to the data.

## Stock vs. FII detection

When the parser finds a table with "ATIVO" + "QUANTIDADE" headers, it needs to determine if it's stocks or FIIs. Three strategies, in priority order:

1. **Page context** — if page text contains "Ações" → stocks; "Fundos Imobili" → FIIs (fastest, most reliable)
2. **Ticker suffix** — if first ticker ends with "11" or "12" → FIIs (e.g., TRXF11, XPML12)
3. **Order fallback** — first unidentified table → stocks; second → FIIs (fragile, last resort)

Strategy 3 only triggers if the page text doesn't contain identifying keywords AND the tickers don't match FII patterns. In practice, strategies 1 and 2 handle all our PDFs.

## File relationships

```
data/reports/*.pdf          ← input (you add these)
        ↓ main.py
data/parsed/YYYY-MM.json    ← generated (parser output)
        ↓ storage.py
app.py / pages/detalhes.py  ← reads JSON, renders dashboard
        ↑
data/contributions.json     ← manual aportes (edited via UI or manually)
```
