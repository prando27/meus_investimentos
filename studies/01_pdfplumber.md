# pdfplumber — PDF Text & Table Extraction

> Docs: https://github.com/jsvine/pdfplumber

## What it does

pdfplumber opens a PDF and gives you programmatic access to every character, line, rectangle, and image on each page. Unlike PyPDF2 (which extracts raw text streams), pdfplumber understands the visual layout and can reconstruct tables.

## Core concepts

### Opening a PDF

```python
import pdfplumber

with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]  # zero-indexed
    print(len(pdf.pages))  # total pages
```

The `with` block ensures the file handle is properly closed.

### Extracting text

```python
text = page.extract_text()
# Returns a single string with newlines between visual lines
# e.g. "Patrimônio em 31/01/2026\nR$ 1.243.581,34"
```

**How it works:** pdfplumber groups characters by their vertical position (y-coordinate) into lines, then sorts left-to-right within each line. It inserts spaces where gaps between characters exceed a threshold.

**Gotcha in this project:** Numbers like `R$ 66.562,47` get extracted as `R$ 66  562,47` — the dot (`.`) is a visual element with spacing that pdfplumber interprets as a gap. This is why `parse_br_number()` strips all spaces before parsing.

### Extracting tables

```python
tables = page.extract_tables()
# Returns a list of tables, each table is a list of rows,
# each row is a list of cell strings (or None)

for table in tables:
    header = table[0]   # ['ATIVO', 'QUANTIDADE', 'VALOR (R$)', 'PERCENTUAL (%)']
    for row in table[1:]:
        print(row)      # ['BBAS3', '2255', 'R$ 56  871,10', '20  1%']
```

**How it works:** pdfplumber detects tables by finding intersecting horizontal and vertical lines (rules) on the page. It then identifies cells as the rectangles formed by these intersections and extracts the text within each cell.

**Table settings:** You can customize detection with `table_settings`:

```python
tables = page.extract_tables(table_settings={
    "vertical_strategy": "lines",     # or "text", "explicit"
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,              # pixel tolerance for aligning lines
    "join_tolerance": 3,
})
```

In this project we use the defaults, which work well for the AUVP reports.

### Extracting words with positions

```python
words = page.extract_words()
# Each word is a dict:
# {'text': 'Patrimônio', 'x0': 48.0, 'top': 85.0, 'x1': 150.0, 'bottom': 100.0, ...}
```

This is useful for debugging — we used it to find that the "Proventos:" heading is at `top=351` but the chart image starts at `top=380`, helping us set the right threshold for OCR.

### Extracting characters

```python
chars = page.chars
# Each char is a dict with x0, top, text, fontname, size, etc.
```

We used this to confirm that between the "Proventos:" heading and the footer, there were zero characters — proving the chart was entirely an image.

### Images

```python
images = page.images
# Each image: {'x0': 48, 'top': 413, 'width': 499, 'height': 333, ...}
```

Images in PDFs are raster bitmaps embedded in the page. pdfplumber tells you their position and size but doesn't decode them — that's where we hand off to OCR.

### Cropping

```python
bbox = (x0, top, x1, bottom)  # left, top, right, bottom
cropped = page.crop(bbox)
# cropped is a new page-like object with only content inside the bbox
text = cropped.extract_text()
```

We crop the proventos chart area before sending it to OCR:

```python
bbox = (chart_img["x0"], chart_img["top"],
        chart_img["x0"] + chart_img["width"],
        chart_img["top"] + chart_img["height"])
cropped = page.crop(bbox)
```

### Converting to image

```python
img = page.to_image(resolution=300)  # returns a PageImage object
img.save("debug.png")                # save for inspection
pil_img = img.original               # get the PIL.Image object
```

The `resolution` parameter controls DPI. Higher = more detail but slower. We found 400 DPI optimal for proventos chart OCR.

## Debugging tips

When a table isn't extracting correctly:

```python
# Visual debug — saves an image showing detected lines and cells
img = page.to_image()
img.debug_tablefinder()
img.save("debug_tables.png")
```

When text isn't where you expect:

```python
# Print all words with positions
for w in page.extract_words():
    print(f"x={w['x0']:.0f} y={w['top']:.0f} '{w['text']}'")
```

## The `.to_image()` → `.original` pattern

When you convert a cropped page to an image for OCR, `.to_image()` returns a `PageImage` object (pdfplumber's wrapper), not a PIL Image directly. You need `.original` to get the actual `PIL.Image`:

```python
cropped = page.crop(bbox)
page_image = cropped.to_image(resolution=400)   # PageImage object
pil_img = page_image.original                    # PIL.Image.Image

# Now you can do PIL operations:
pil_img = pil_img.convert("L")                   # grayscale
```

The `resolution` parameter is DPI (dots per inch). Higher DPI = more pixels = more detail for OCR, but slower. At 300 DPI, a 500pt-wide crop becomes ~2000px wide.

## Merged cells and the newline trick

When pdfplumber encounters a table cell that spans multiple visual rows (merged cell), it concatenates all text in that cell with `\n` separators:

```python
# Old-format fixed income table extracts as:
['%CDI\nPRE\nIPCA+\nSELIC+', '118,43%\n13,09%\n7,32%\n0,10%', ...]

# Detection: if the first cell has \n, it's a merged format
if "\n" in row[0]:
    indexers = row[0].split("\n")      # ['%CDI', 'PRE', 'IPCA+', 'SELIC+']
    rates = row[1].split("\n")          # ['118,43%', '13,09%', '7,32%', '0,10%']
    values = row[2].split("\n")         # ['R$ 62.504,12', ...]
    # Iterate in parallel:
    for i, indexer in enumerate(indexers):
        process(indexer, rates[i], values[i])
```

This is how `_parse_fixed_income_page()` handles the old PDF format. The key insight: **newlines inside a cell = merged rows**.

## Images in PDFs

`page.images` returns metadata about embedded raster bitmaps — position and size, but NOT the pixel data:

```python
images = page.images
# {'x0': 48, 'top': 413, 'width': 499, 'height': 333, ...}
```

To actually "see" the image content, you need to:
1. Crop the page to the image's bounding box
2. Convert the crop to a PIL Image via `.to_image().original`

This is an indirect process because pdfplumber renders the entire page as an image, then you crop the area where the embedded image sits. You're not extracting the original embedded bitmap — you're re-rendering it.

## Limitations

- **Cannot extract text from images** — if text is rendered as part of a raster image (like chart labels), pdfplumber sees nothing. You need OCR.
- **Table detection depends on visible lines** — tables without borders or with only partial borders may not be detected.
- **Merged cells** — pdfplumber extracts them as a single cell with newlines inside (see above).
- **Scanned PDFs** — if the entire PDF is a scanned image, pdfplumber extracts nothing. You'd need OCR for the whole thing. Our PDFs are digitally generated (not scanned), so most content is extractable.
- **Fragile text extraction** — `extract_text()` reconstructs lines by grouping characters at similar y-coordinates. If the PDF has unusual spacing or overlapping elements, the result can be garbled. Our parser relies on regex over extracted text, which works because AUVP reports have clean, consistent layouts.
