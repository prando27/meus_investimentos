"""Parse AUVP Capital monthly PDF reports into structured data."""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from src.models import (
    FII,
    FIISegment,
    FixedIncomeAsset,
    MonthlyReport,
    Movement,
    PortfolioAllocation,
    Proventos,
    SectorDistribution,
    Stock,
    TargetAllocation,
)


def parse_br_number(text: str) -> float:
    """Convert Brazilian number format to float.

    Handles both standard '1.234,56' and PDF-extracted '1  234,56' with spaces.
    Also handles OCR artifacts like '1.22359' (dropped comma → '1.223,59').
    """
    if not text:
        return 0.0
    text = text.strip()
    text = re.sub(r"R\$\s*", "", text)
    negative = text.startswith("-")
    if negative:
        text = text[1:].strip()
    # Remove all spaces (PDF extracts thousands with spaces)
    text = text.replace(" ", "")

    # Handle OCR-dropped comma: "1.22359" → should be "1.223,59"
    # Pattern: dot followed by 4+ digits with no comma = OCR dropped the comma
    if "," not in text and re.match(r"^\d+\.\d{4,}$", text):
        # Insert comma before last 2 digits
        text = text[:-2] + "," + text[-2:]

    # Remove thousand-separator dots, convert decimal comma
    text = text.replace(".", "").replace(",", ".")
    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return 0.0


def parse_br_percentage(text: str) -> float:
    """Convert '4,40%' or '4  40%' to 4.40.

    In PDF extraction, spaces replace the decimal dot: '9  74%' means '9.74%'.
    """
    if not text:
        return 0.0
    text = text.strip().replace("%", "")
    # Replace space groups with dot (PDF uses spaces instead of decimal dot)
    text = re.sub(r"\s+", ".", text)
    # Also handle comma as decimal separator
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _clean_ticker(ticker: str) -> str:
    """Fix tickers that have spaces inserted by PDF extraction (e.g. 'AL  P11' -> 'ALUP11')."""
    return ticker.replace(" ", "")


def _extract_month_from_filename(filename: str) -> str:
    """Extract month from filename like 'Janeiro 2026 - ...'."""
    month_map = {
        "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
        "abril": "04", "maio": "05", "junho": "06",
        "julho": "07", "agosto": "08", "setembro": "09",
        "outubro": "10", "novembro": "11", "dezembro": "12",
    }
    name_lower = filename.lower()
    for month_name, month_num in month_map.items():
        if month_name in name_lower:
            year_match = re.search(r"(\d{4})", filename)
            if year_match:
                year = year_match.group(1)
                import calendar
                last_day = calendar.monthrange(int(year), int(month_num))[1]
                return f"{year}-{month_num}-{last_day:02d}"
    return ""


def _parse_summary_page(page) -> dict:
    """Parse page 2: summary metrics + portfolio table."""
    text = page.extract_text() or ""
    result = {}

    # Patrimônio - first R$ value on the page
    m = re.search(r"R\$\s*([\d\s.,]+)\n", text)
    if m:
        result["patrimony"] = parse_br_number(m.group(1))

    # Rentabilidade no mês
    m = re.search(r"(\d[\d\s,]+%)\s*R\$", text)
    if m:
        result["monthly_return_pct"] = parse_br_percentage(m.group(1))

    # Ganhos financeiros no mês
    m = re.search(r"Ganhos financeiros no m[eê]s\n(\d[\d\s,]+%)\s*R\$\s*([\d\s.,]+)", text)
    if m:
        result["monthly_gains"] = parse_br_number(m.group(2))
    else:
        # Try: after percentage and R$
        m = re.search(r"[\d,]+%\s+R\$\s*([\d\s.,]+)\n", text)
        if m:
            result["monthly_gains"] = parse_br_number(m.group(1))

    # Aplicações no mês
    m = re.search(r"Aplica[çc][õo]es no m[eê]s\s+Movimenta", text)
    if m:
        # Values are on the next line
        after = text[m.end():]
        m2 = re.search(r"R\$\s*([\d\s.,]+)\s+(-?)R\$\s*([\d\s.,]+)", after)
        if m2:
            result["applications"] = parse_br_number(m2.group(1))
            movements_val = parse_br_number(m2.group(3))
            if m2.group(2) == "-":
                movements_val = -movements_val
            result["movements_net"] = movements_val

    # Portfolio from single-column table or text
    portfolio = []
    asset_classes = ["Renda Fixa", "Ações", "Internacional", "FIIs", "COE"]
    for ac in asset_classes:
        m = re.search(rf"{re.escape(ac)}\s+R\$\s*([\d\s.,]+)", text)
        if m:
            portfolio.append(PortfolioAllocation(
                asset_class=ac,
                value=parse_br_number(m.group(1)),
                percentage=0.0,
            ))
    total = sum(p.value for p in portfolio)
    if total > 0:
        for p in portfolio:
            p.percentage = round(p.value / total * 100, 2)
    result["portfolio"] = portfolio

    return result


def _ocr_proventos_chart(page) -> str:
    """OCR the proventos chart image region to extract values."""
    try:
        from PIL import ImageFilter
        import pytesseract

        # Find the chart image on the page (largest image below "Proventos:")
        images = page.images
        chart_img = None
        for img in images:
            if img["top"] > 300 and img["width"] > 200:
                chart_img = img
                break
        if not chart_img:
            return ""

        # Crop and OCR the chart area at 400 DPI with sharpening for accuracy
        bbox = (chart_img["x0"], chart_img["top"],
                chart_img["x0"] + chart_img["width"],
                chart_img["top"] + chart_img["height"])
        cropped = page.crop(bbox)
        pil_img = cropped.to_image(resolution=400).original
        pil_img = pil_img.convert("L").filter(ImageFilter.SHARPEN)
        return pytesseract.image_to_string(pil_img)
    except ImportError:
        return ""
    except Exception:
        return ""


def _parse_movements_page(page) -> dict:
    """Parse page 3: acquired assets + proventos."""
    text = page.extract_text() or ""
    result = {}

    # Acquired assets from table
    acquired = []
    tables = page.extract_tables()
    for table in tables:
        for row in table:
            if not row or not row[0]:
                continue
            name = row[0].strip()
            if name in ("CLASSE DE ATIVO", ""):
                continue
            val_text = row[-1] if len(row) > 1 and row[-1] else row[0]
            if val_text and name:
                acquired.append(Movement(
                    asset_class=name, value=parse_br_number(val_text)
                ))
    result["acquired_assets"] = acquired

    # Proventos - chart labels are images, use OCR on the chart region
    acoes = fiis = cupons = total_prov = 0.0
    prov_text = ""

    # First try extractable text after "Proventos:"
    prov_idx = text.find("Proventos:")
    if prov_idx >= 0:
        prov_text = text[prov_idx:]

    # If no values found in text, OCR the proventos chart image
    if "R$" not in prov_text.replace("Proventos:", ""):
        prov_text = _ocr_proventos_chart(page)

    # OCR produces many variants: "Ações", "Acées", "Acdes", "AcGées", etc.
    m = re.search(r"Ac[^\s:]*s:?\s*R\$\s*([\d\s.,]+)", prov_text)
    if m:
        acoes = parse_br_number(m.group(1))
    m = re.search(r"F[Ii][Il]s:?\s*R\$\s*([\d\s.,]+)", prov_text)
    if m:
        fiis = parse_br_number(m.group(1))
    m = re.search(r"Cupons?\s*R[.\-]?\s*F[.\-]?:?\s*R\$\s*([\d\s.,]+)", prov_text)
    if m:
        cupons = parse_br_number(m.group(1))
    # Total is always the sum (the standalone R$ line in OCR may be ambiguous)
    total_prov = acoes + fiis + cupons
    result["proventos"] = Proventos(acoes=acoes, fiis=fiis, cupons_rf=cupons, total=total_prov)

    return result


def _parse_fixed_income_page(page) -> list[FixedIncomeAsset]:
    """Parse fixed income indexers table. Handles both formats:
    - New: separate rows per indexer
    - Old: all indexers in a single merged cell with newlines
    """
    assets = []
    tables = page.extract_tables()
    for table in tables:
        for row in table:
            if not row or not row[0]:
                continue
            first_cell = row[0].strip()
            if first_cell.lower() in ("indexador", "indexadores"):
                continue

            # Check if it's the old merged-cell format (newlines inside cells)
            if "\n" in first_cell:
                indexers = first_cell.split("\n")
                rates = (row[1] or "").strip().split("\n") if len(row) > 1 and row[1] else []
                values = (row[2] or "").strip().split("\n") if len(row) > 2 and row[2] else []
                pcts = (row[3] or "").strip().split("\n") if len(row) > 3 and row[3] else []
                for i, indexer in enumerate(indexers):
                    indexer = indexer.strip()
                    if not indexer or indexer.lower() in ("indexador", "total:"):
                        continue
                    assets.append(FixedIncomeAsset(
                        indexer=indexer,
                        avg_rate=rates[i].strip() if i < len(rates) else "",
                        value=parse_br_number(values[i]) if i < len(values) else 0.0,
                        percentage=parse_br_percentage(pcts[i]) if i < len(pcts) else 0.0,
                    ))
                return assets

            # New format: one row per indexer
            indexer = first_cell
            if indexer.upper() in ("INDEXADOR", "TOTAL:") or indexer == "":
                continue
            if len(row) >= 4:
                assets.append(FixedIncomeAsset(
                    indexer=indexer,
                    avg_rate=row[1].strip() if row[1] else "",
                    value=parse_br_number(row[2]) if row[2] else 0.0,
                    percentage=parse_br_percentage(row[3]) if row[3] else 0.0,
                ))
    return assets


def _parse_sector_distribution(page) -> list[SectorDistribution]:
    """Parse sector distribution from the Ações section page."""
    text = page.extract_text() or ""
    sectors = []
    # Pattern: "Bancos R$ 79.163,20 (27.9%)" — but spaces may be in numbers
    for m in re.finditer(
        r"([A-ZÀ-Úa-zà-ú][A-ZÀ-Úa-zà-ú /]+?)\s+R\$\s*([\d\s.,]+)\s*\(([\d\s.,]+)%\)", text
    ):
        sector = m.group(1).strip()
        # Filter out page headers/noise
        if sector and len(sector) > 2 and "auvp" not in sector.lower():
            sectors.append(SectorDistribution(
                sector=sector,
                value=parse_br_number(m.group(2)),
                percentage=parse_br_percentage(m.group(3) + "%"),
            ))
    return sectors


def _parse_fii_segments(page) -> list[FIISegment]:
    """Parse FII segment distribution page."""
    text = page.extract_text() or ""
    segments = []
    for m in re.finditer(
        r"([A-ZÀ-Úa-zà-ú][A-ZÀ-Úa-zà-ú ]+?)\s+R\$\s*([\d\s.,]+)\s*\(([\d\s.,]+)%\)", text
    ):
        segment = m.group(1).strip()
        if segment and len(segment) > 2 and "auvp" not in segment.lower():
            segments.append(FIISegment(
                segment=segment,
                value=parse_br_number(m.group(2)),
                percentage=parse_br_percentage(m.group(3) + "%"),
            ))
    return segments


def _parse_asset_table(page, asset_cls):
    """Parse a stocks or FIIs table (ATIVO, QUANTIDADE, VALOR, PERCENTUAL)."""
    assets = []
    tables = page.extract_tables()
    for table in tables:
        for row in table:
            if not row or not row[0]:
                continue
            ticker = _clean_ticker(row[0].strip())
            if ticker in ("ATIVO", "Total:", ""):
                continue
            if len(row) >= 4:
                try:
                    qty_str = row[1].strip().replace(" ", "") if row[1] else "0"
                    qty = int(qty_str)
                except ValueError:
                    continue
                assets.append(asset_cls(
                    ticker=ticker,
                    quantity=qty,
                    value=parse_br_number(row[2]) if row[2] else 0.0,
                    percentage=parse_br_percentage(row[3]) if row[3] else 0.0,
                ))
    return assets


def _find_page_by_title(pages, title: str) -> int | None:
    """Find page index containing a specific title."""
    for i, page in enumerate(pages):
        text = page.extract_text() or ""
        if title.lower() in text.lower():
            return i
    return None


def _parse_old_summary_page(page) -> dict:
    """Parse old-format summary (e.g. Aug 2025): single-row tables for metrics and portfolio."""
    text = page.extract_text() or ""
    result = {}
    tables = page.extract_tables()

    # First table: Patrimônio inicial | Movimentações | Patrimônio final | Rentabilidade % | Rendimentos
    if tables:
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [c.strip() if c else "" for c in table[0]]
            if "Patrimônio final" in header or "Patrimônio final" in " ".join(header):
                row = table[1]
                # Find column indices
                for i, h in enumerate(header):
                    if "final" in h.lower():
                        result["patrimony"] = parse_br_number(row[i])
                    elif "rentabilidade" in h.lower():
                        result["monthly_return_pct"] = parse_br_percentage(row[i])
                    elif "rendimentos" in h.lower():
                        result["monthly_gains"] = parse_br_number(row[i])
                    elif h.lower() == "movimentações":
                        result["movements_net"] = parse_br_number(row[i])

    # Portfolio table: Renda Fixa | Ações | FIIs | Internacional | COE (horizontal)
    portfolio = []
    asset_classes = ["Renda Fixa", "Ações", "FIIs", "Internacional", "COE"]
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [c.strip() if c else "" for c in table[0]]
        if any(ac in header for ac in asset_classes):
            row = table[1]
            for i, h in enumerate(header):
                h = h.strip()
                if h in asset_classes and i < len(row):
                    portfolio.append(PortfolioAllocation(
                        asset_class=h,
                        value=parse_br_number(row[i]),
                        percentage=0.0,
                    ))
            break
    total = sum(p.value for p in portfolio)
    if total > 0:
        for p in portfolio:
            p.percentage = round(p.value / total * 100, 2)
    result["portfolio"] = portfolio

    # Applications not directly available in old format
    result.setdefault("applications", 0.0)

    return result


def _detect_layout(pages) -> str:
    """Detect PDF layout: 'new' (2025-11+) or 'old' (earlier)."""
    # New layout has "Resumo da Carteira" on page 2
    if len(pages) > 1:
        text = pages[1].extract_text() or ""
        if "Resumo da Carteira" in text:
            return "new"
    return "old"


def parse_pdf(pdf_path: str | Path) -> MonthlyReport:
    """Parse an AUVP Capital monthly PDF report."""
    pdf_path = Path(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages
        layout = _detect_layout(pages)

        report_date = _extract_month_from_filename(pdf_path.name)

        if layout == "new":
            summary = _parse_summary_page(pages[1])
            if not report_date:
                text = pages[1].extract_text() or ""
                m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
                if m:
                    report_date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            movements_data = _parse_movements_page(pages[2])
        else:
            # Old layout: summary on the page with "Principais números"
            summary_page = _find_page_by_title(pages, "Principais números")
            if summary_page is not None:
                summary = _parse_old_summary_page(pages[summary_page])
                movements_data = _parse_movements_page(pages[summary_page])
            else:
                summary = {}
                movements_data = {"acquired_assets": [], "proventos": Proventos(0, 0, 0, 0)}

        # Find pages by title for robustness
        fi_page = _find_page_by_title(pages, "Indexadores de Ativos de Renda Fixa")
        if fi_page is None:
            fi_page = _find_page_by_title(pages, "Indexador")
        sector_page = _find_page_by_title(pages, "Distribuição setorial")
        fii_seg_page = _find_page_by_title(pages, "Distribuição por Segmentos")

        # Fixed income
        fixed_income = []
        if fi_page is not None:
            fixed_income = _parse_fixed_income_page(pages[fi_page])

        # Sector distribution
        sector_distribution = []
        if sector_page is not None:
            sector_distribution = _parse_sector_distribution(pages[sector_page])

        # FII segments
        fii_segments = []
        if fii_seg_page is not None:
            fii_segments = _parse_fii_segments(pages[fii_seg_page])

        # Find stock and FII asset tables — they have "ATIVO" + "QUANTIDADE" headers
        stocks = []
        fiis = []
        for i, page in enumerate(pages):
            text = page.extract_text() or ""
            tables = page.extract_tables()
            for table in tables:
                if not table or not table[0]:
                    continue
                header = [c.strip() if c else "" for c in table[0]]
                if "ATIVO" in header and "QUANTIDADE" in header:
                    # Determine if stocks or FIIs based on page context
                    if "Ações" in text or "setorial" in text.lower():
                        stocks = _parse_asset_table(page, Stock)
                    elif "Fundos Imobili" in text or "Segmentos" in text:
                        fiis = _parse_asset_table(page, FII)
                    else:
                        # Check tickers — FIIs end with 11/12
                        sample = _parse_asset_table(page, Stock)
                        if sample and sample[0].ticker.endswith(("11", "12")):
                            fiis = [FII(s.ticker, s.quantity, s.value, s.percentage) for s in sample]
                        else:
                            if not stocks:
                                stocks = sample
                            else:
                                fiis = [FII(s.ticker, s.quantity, s.value, s.percentage) for s in sample]

        # Target allocation — calculate from portfolio percentages or use known targets
        target_allocation = []
        # Try to extract from page 4 text (may be chart-only)
        alloc_page = _find_page_by_title(pages, "Alocação por Estratégia")
        if alloc_page is not None:
            alloc_text = pages[alloc_page].extract_text() or ""
            # Extract percentages from chart labels if available
            targets = re.findall(
                r"(Internacional|Ações|FIIs|Renda Fixa|R\.\s*F\.\s*Internacional|COE)\s*\(?([\d\s.,]+)%\)?",
                alloc_text,
            )
            if targets:
                # The second occurrence of each class is the target
                seen = {}
                for cls, pct in targets:
                    cls = cls.strip()
                    if cls in seen:
                        target_allocation.append(TargetAllocation(
                            asset_class=cls,
                            percentage=parse_br_percentage(pct + "%"),
                        ))
                    seen[cls] = True

    return MonthlyReport(
        date=report_date,
        patrimony=summary.get("patrimony", 0.0),
        monthly_return_pct=summary.get("monthly_return_pct", 0.0),
        monthly_gains=summary.get("monthly_gains", 0.0),
        applications=summary.get("applications", 0.0),
        movements=summary.get("movements_net", 0.0),
        portfolio=summary.get("portfolio", []),
        target_allocation=target_allocation,
        fixed_income=fixed_income,
        stocks=stocks,
        fiis=fiis,
        sector_distribution=sector_distribution,
        fii_segments=fii_segments,
        proventos=movements_data.get("proventos"),
        acquired_assets=movements_data.get("acquired_assets", []),
    )
