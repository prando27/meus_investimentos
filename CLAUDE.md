# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run python main.py              # Parse all PDFs in data/reports/ → JSON in data/parsed/
uv run streamlit run app.py         # Run the dashboard (http://localhost:8501)
APP_PASSWORD=xxx uv run streamlit run app.py  # Run with auth enabled
uv sync                             # Install/update dependencies
```

## Architecture

Investment portfolio dashboard that parses AUVP Capital monthly PDF reports into structured JSON data, then visualizes it via Streamlit.

**Data flow:** `PDF → parser.py (pdfplumber + OCR) → JSON → storage.py → app.py (Streamlit + Plotly)`

### Source files

- `src/parser.py` — PDF extraction engine. Detects two PDF layouts automatically:
  - **New format** (Nov 2025+): "Resumo da Carteira" on page 2, separate tables per section, multi-page reports (~10 pages)
  - **Old format** (before Nov 2025): "Principais números" with horizontal summary tables, merged cells in fixed income, fewer pages (~8 pages)
  - Uses `_detect_layout()` to choose the right parsing path
  - Uses pdfplumber for text/tables, pytesseract OCR for chart-embedded proventos data
  - Finds pages by title (`_find_page_by_title`) for robustness across format variations
- `src/models.py` — Dataclasses for all report data. `MonthlyReport` is the root with nested portfolio, stocks, FIIs, fixed income, proventos, etc. Serializes to/from JSON via `to_dict()`/`from_dict()`.
- `src/storage.py` — JSON persistence in `data/parsed/YYYY-MM.json`. Tracks parsed months to skip duplicates.
- `src/auth.py` — Simple password gate. Reads `APP_PASSWORD` from env var or Streamlit secrets. Does nothing when unset (local dev). Uses `hmac.compare_digest` for timing-safe comparison.
- `main.py` — CLI that batch-processes PDFs from `data/reports/`, skipping already-parsed months.
- `app.py` — Main dashboard: summary metrics, patrimony evolution with period selector, aportes tracking (BTG Pactual), rentabilidade mensal + acumulada with period selector, proventos evolution.
- `pages/detalhes.py` — Detail page: allocation pie + target comparison, fixed income by indexer, stocks + sector distribution, FIIs + segment distribution, acquired assets.
- `data/contributions.json` — Manual monthly contribution amounts (aportes BTG Pactual), edited via sidebar form in the dashboard.

## PDF Parsing Pitfalls

These are hard-won lessons from debugging the parser:

- **Spaces replace dots in numbers**: pdfplumber extracts `R$ 66  562,47` instead of `R$ 66.562,47`. `parse_br_number()` strips all spaces before parsing.
- **Spaces replace decimal dots in percentages**: `9  74%` means `9.74%`. `parse_br_percentage()` replaces space groups with `.` (not just removes them).
- **OCR drops commas**: tesseract sometimes reads `R$ 1.982,54` as `R$ 1.98254`. `parse_br_number()` detects this pattern (dot + 4+ digits, no comma) and inserts the comma before the last 2 digits.
- **OCR mangles Portuguese**: "Ações" → "Acées", "Acdes", "AcGées", "Ac6es". The proventos regex uses `Ac[^\s:]*s` to match all variants. "FIIs" → "Fils".
- **Tickers have spaces**: `AL  P11` → `ALUP11`, `IT  B4` → `ITUB4`. `_clean_ticker()` strips all spaces.
- **Proventos chart is an image**: The chart with proventos breakdown (ações, FIIs, cupons RF) is rendered as a raster image in the PDF, not extractable text. OCR at 400 DPI with grayscale + sharpen gives best results. The chart image threshold is `top > 300` to handle both old and new formats.
- **Old format fixed income uses merged cells**: All indexers in a single cell separated by `\n`. The parser splits on newlines when detected.
- **Old format stocks/FIIs are chart images only**: No extractable table data for individual holdings in pre-Nov 2025 reports.

## Key Conventions

- PDF filenames use underscores: `{Mês}_{Ano}_-_{Nome}_-_{ID}.pdf` (e.g. `Janeiro_2026_-_Jose_Antonio_Nazario_Prando_-_008588553.pdf`)
- `_extract_month_from_filename()` matches Portuguese month names case-insensitively, works with both spaces and underscores
- Source code in English, UI strings in Portuguese
- System dependency: `tesseract` must be installed for proventos OCR (`brew install tesseract` on macOS, `apt-get install tesseract-ocr` in Docker)
- Aportes (contributions) are exclusively for BTG Pactual
- Dashboard is responsive for both desktop and mobile (iPhone 16 Pro tested) — metrics in 2-column grid, charts use hover instead of text labels, horizontal legends

## Deployment

- **Dockerfile** included for Railway deployment
- Auth: set `APP_PASSWORD` env var in production; unset locally for no-auth dev
- PDFs and parsed JSON are committed to the repo (private repo) for deployment
- Railway auto-deploys on `git push`
