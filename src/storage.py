"""JSON storage for parsed monthly reports."""

from __future__ import annotations

import json
from pathlib import Path

from src.models import MonthlyReport

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "parsed"


def save_report(report: MonthlyReport) -> Path:
    """Save a report as JSON. Filename is YYYY-MM.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # date is YYYY-MM-DD, use YYYY-MM for filename
    month_key = report.date[:7]
    path = DATA_DIR / f"{month_key}.json"
    path.write_text(report.to_json(), encoding="utf-8")
    return path


def load_all_reports() -> list[MonthlyReport]:
    """Load all parsed reports, sorted by date."""
    if not DATA_DIR.exists():
        return []
    reports = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        reports.append(MonthlyReport.from_dict(data))
    return reports


def get_parsed_months() -> set[str]:
    """Return set of already-parsed month keys (YYYY-MM)."""
    if not DATA_DIR.exists():
        return set()
    return {p.stem for p in DATA_DIR.glob("*.json")}
