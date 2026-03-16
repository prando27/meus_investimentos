"""CLI entry point: scan data/reports/ for PDFs, parse and save as JSON."""

from pathlib import Path

from src.parser import parse_pdf
from src.storage import get_parsed_months, save_report

REPORTS_DIR = Path(__file__).resolve().parent / "data" / "reports"


def main():
    if not REPORTS_DIR.exists():
        print(f"Reports directory not found: {REPORTS_DIR}")
        return

    pdfs = list(REPORTS_DIR.glob("*.pdf"))
    if not pdfs:
        print("No PDF files found in data/reports/")
        return

    parsed = get_parsed_months()
    new_count = 0

    for pdf_path in sorted(pdfs):
        print(f"Processing: {pdf_path.name}")
        try:
            report = parse_pdf(pdf_path)
            month_key = report.date[:7]
            if month_key in parsed:
                print(f"  Already parsed ({month_key}), skipping.")
                continue
            out = save_report(report)
            print(f"  Saved: {out}")
            new_count += 1
        except Exception as e:
            print(f"  Error parsing {pdf_path.name}: {e}")

    print(f"\nDone. {new_count} new report(s) parsed.")


if __name__ == "__main__":
    main()
