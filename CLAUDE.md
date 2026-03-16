# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run python main.py              # Parse all PDFs in data/reports/ → JSON in data/parsed/
uv run streamlit run app.py         # Run the dashboard (http://localhost:8501)
uv sync                             # Install/update dependencies
```

## Architecture

Investment portfolio dashboard that parses AUVP Capital monthly PDF reports into structured JSON data, then visualizes it via Streamlit.

**Data flow:** `PDF → parser.py (pdfplumber + OCR) → JSON → storage.py → app.py (Streamlit + Plotly)`

- `src/parser.py` — PDF extraction engine. Uses pdfplumber for text/tables, pytesseract OCR for chart-embedded data (proventos). Finds pages by title for robustness. Handles Brazilian number format (`1.234,56`) and PDF extraction artifacts (spaces replacing dots in numbers, mangled tickers).
- `src/models.py` — Dataclasses for all report data. `MonthlyReport` is the root with nested portfolio, stocks, FIIs, fixed income, proventos, etc. Serializes to/from JSON via `to_dict()`/`from_dict()`.
- `src/storage.py` — JSON persistence in `data/parsed/YYYY-MM.json`. Tracks parsed months to skip duplicates.
- `main.py` — CLI that batch-processes PDFs from `data/reports/`, skipping already-parsed months.
- `app.py` — Streamlit dashboard with Plotly charts. Month selector, allocation donuts, asset tables, sector/segment breakdowns.

## Key Conventions

- Brazilian number parsing: `parse_br_number()` and `parse_br_percentage()` handle both standard format and PDF-extracted format with spaces
- PDF filenames follow pattern: `{Mês em português} {Ano} - {Nome} - {ID}.pdf`
- Source code in English, UI strings in Portuguese
- System dependency: `tesseract` must be installed for proventos OCR (`brew install tesseract`)
