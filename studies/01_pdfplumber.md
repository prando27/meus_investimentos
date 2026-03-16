# pdfplumber — PDF Text & Table Extraction

> Docs: https://github.com/jsvine/pdfplumber

## What is a PDF, really?

Before understanding pdfplumber, you need to know what a PDF actually contains. A PDF is **not** like an HTML page or a Word document. It doesn't store "paragraphs" or "tables" as structured data. Instead, a PDF is essentially a **drawing instruction set** — it says things like:

- "Draw the character 'R' at position (48, 200) in font Montserrat-Bold size 14"
- "Draw the character '$' at position (58, 200)"
- "Draw a horizontal line from (40, 300) to (550, 300) with 1pt width"
- "Place this 499x333 pixel image at position (48, 413)"

There's no concept of "this is a table" or "this is a paragraph" in the PDF itself. What looks like a table to your eyes is actually just characters carefully positioned between drawn lines. What looks like a paragraph is characters positioned in sequence with line breaks at certain y-coordinates.

This is why extracting structured data from PDFs is hard — you have to **reverse-engineer** the visual layout from raw drawing instructions.

## What pdfplumber does

**pdfplumber** is a Python library that reads PDF files and reconstructs the visual layout. It:

1. Reads all the drawing instructions (characters, lines, rectangles, images)
2. Groups characters into words based on spacing
3. Groups words into lines based on vertical alignment
4. Detects tables by finding intersecting lines that form grid patterns
5. Extracts text from within each detected cell

It builds on **pdfminer.six** (a lower-level PDF parser that extracts raw characters) and adds the layout intelligence on top.

**Why pdfplumber over alternatives?**

| Library | Strength | Weakness |
|---------|----------|----------|
| **PyPDF2/pypdf** | Fast, simple text extraction | No layout awareness, tables come as jumbled text |
| **pdfminer.six** | Low-level access to every character | No table detection, you build layout logic yourself |
| **pdfplumber** | Table detection, layout-aware text, cropping, visual debugging | Slower than PyPDF2, can't handle scanned PDFs |
| **tabula-py** | Java-based table extraction (uses Tabula) | Requires Java runtime, less flexible than pdfplumber |
| **camelot** | Excellent table extraction | Requires Ghostscript, focused only on tables |

pdfplumber is the best all-rounder for our use case: we need both text extraction and table extraction, with the ability to crop specific regions for OCR.

## Core concepts

### PDF coordinate system

Every position in a PDF uses a coordinate system measured in **points** (1 point = 1/72 of an inch). The origin (0, 0) is at the **top-left** corner of the page:

```
(0, 0) ──────────────────── x increases →
  │
  │    "Patrimônio" at (48, 85)
  │
  │    Table at (40, 187) to (550, 320)
  │
  │    Chart image at (48, 413), size 499x333
  │
  y increases ↓
```

All coordinates in pdfplumber use this system. When you see `'x0': 48, 'top': 85`, that means 48 points from the left edge, 85 points from the top.

Key coordinate properties:
- **x0** — left edge of the element
- **x1** — right edge
- **top** — top edge (distance from page top)
- **bottom** — bottom edge
- **width** — x1 - x0
- **height** — bottom - top

### Opening a PDF

```python
import pdfplumber

with pdfplumber.open("report.pdf") as pdf:
    page = pdf.pages[0]  # zero-indexed: pages[0] is page 1
    print(len(pdf.pages))  # total page count
```

The `with` block is a **context manager** — it ensures the file handle is properly closed when you're done, even if an error occurs. Always use this pattern with pdfplumber.

`pdf.pages` is a list of `Page` objects. Each page contains all the drawing instructions for that page.

### Extracting text

```python
text = page.extract_text()
# Returns a single string with newlines between visual lines
# e.g. "Patrimônio em 31/01/2026\nR$ 1.243.581,34"
```

**How it works internally:**

1. pdfplumber reads all character objects on the page (each has text, x, y, font, size)
2. Groups characters into words using a **spacing threshold** — if the gap between two characters is larger than a fraction of the font size, it's a word boundary (inserts a space)
3. Groups words into lines — characters at similar y-coordinates belong to the same line
4. Sorts lines top-to-bottom, characters left-to-right within each line
5. Joins everything with `\n` between lines and spaces between words

**Gotcha in this project:** The Brazilian thousand-separator dot (`.`) in numbers like `R$ 66.562,47` creates a visual gap in the PDF. The characters `66` and `562` are positioned with a small space around the dot. pdfplumber interprets this gap as a word boundary and inserts spaces: `R$ 66  562,47`. This is why our `parse_br_number()` strips all spaces before parsing.

**Gotcha with percentages:** Similarly, `9.74%` becomes `9  74%` — the dot is replaced by spaces. But for percentages, the "dot" was a decimal separator, not a thousands separator. Our `parse_br_percentage()` handles this by replacing space groups with `.` (not just removing them).

### Extracting tables

```python
tables = page.extract_tables()
# Returns: list of tables
# Each table: list of rows
# Each row: list of cell strings (or None for empty cells)

for table in tables:
    header = table[0]   # ['ATIVO', 'QUANTIDADE', 'VALOR (R$)', 'PERCENTUAL (%)']
    for row in table[1:]:
        print(row)      # ['BBAS3', '2255', 'R$ 56  871,10', '20  1%']
```

**How table detection works:**

1. pdfplumber scans the page for **line segments** (horizontal and vertical)
2. It finds **intersections** — where horizontal and vertical lines cross
3. Intersections define the corners of **cells**
4. Groups of connected cells form a **table**
5. Text within each cell's bounding box is extracted

This means table detection depends entirely on **visible lines**. If a table uses only background colors (no borders), pdfplumber won't detect it.

**Table detection strategies:**

```python
tables = page.extract_tables(table_settings={
    "vertical_strategy": "lines",     # detect vertical borders from drawn lines
    "horizontal_strategy": "lines",   # detect horizontal borders from drawn lines
    "snap_tolerance": 3,              # pixel tolerance for aligning nearby lines
    "join_tolerance": 3,              # tolerance for joining line segments
})
```

The strategies can be:
- `"lines"` — use drawn line segments (default, works for our PDFs)
- `"text"` — infer columns from text alignment (useful for borderless tables)
- `"explicit"` — you provide the line positions manually

In this project we use the defaults, which work well for the AUVP reports because they all have bordered tables.

### Extracting words with positions

```python
words = page.extract_words()
# Returns a list of dicts, one per word:
# {
#   'text': 'Patrimônio',
#   'x0': 48.0,     # left edge
#   'top': 85.0,     # top edge
#   'x1': 150.0,     # right edge
#   'bottom': 100.0, # bottom edge
#   'doctop': 85.0,  # top relative to entire document (not just this page)
#   'upright': True,  # True if text is horizontal
# }
```

This is invaluable for **debugging** — when you need to understand the spatial layout of a page. We used it to find that the "Proventos:" heading sits at `top=351` on one PDF and `top=322` on another, while the chart image starts at `top=380` and `top=350` respectively. This helped us choose the right threshold (`top > 300`) for finding the chart image.

### Extracting characters

```python
chars = page.chars
# Each char is a dict:
# {
#   'text': 'P',
#   'x0': 48.0, 'top': 384.0,
#   'fontname': 'PSFDKY+Montserrat-Bold',
#   'size': 14.0,
#   ...
# }
```

This is the lowest-level extraction — every individual character with its exact position, font, and size. We used it to prove that the proventos chart area contained zero text characters (only the "Proventos:" heading), confirming the chart labels were embedded in an image.

### Images

```python
images = page.images
# Each image is a dict with position and size:
# {'x0': 48, 'top': 413, 'width': 499, 'height': 333, 'stream': ..., ...}
```

**What are images in a PDF?** They're **raster bitmaps** (grids of pixels, like a PNG or JPEG) embedded directly in the PDF file. Charts generated by tools like Highcharts are often rendered as bitmaps, not as individual text elements.

pdfplumber tells you **where** each image is on the page and how big it is, but it doesn't give you the pixel data directly. To work with the image content, you need to use the cropping + rendering approach (explained next).

### Cropping

**Cropping** creates a new page-like object that contains only the content within a specified rectangle:

```python
bbox = (x0, top, x1, bottom)  # left, top, right, bottom — in page coordinates
cropped = page.crop(bbox)

# The cropped object behaves like a page:
text = cropped.extract_text()     # only text within the bbox
tables = cropped.extract_tables() # only tables within the bbox
```

The coordinates are **absolute page coordinates** (same system as the original page). The bbox must be within the page bounds.

We crop the proventos chart area before sending it to OCR:

```python
# chart_img is from page.images — it has x0, top, width, height
bbox = (chart_img["x0"], chart_img["top"],
        chart_img["x0"] + chart_img["width"],
        chart_img["top"] + chart_img["height"])
cropped = page.crop(bbox)
```

### Converting to image (rendering)

You can render any page (or cropped region) as a pixel image:

```python
page_image = page.to_image(resolution=300)  # returns a PageImage object
page_image.save("debug.png")                # save to file for inspection
```

**PageImage** is pdfplumber's wrapper object. To get a **PIL Image** (needed for OCR or image processing), access the `.original` attribute:

```python
pil_img = page_image.original    # PIL.Image.Image object
```

The `resolution` parameter is **DPI** (dots per inch). It controls how many pixels are generated per point of the PDF:
- At **72 DPI** (the PDF's native resolution): 1 point = 1 pixel. A 500pt-wide page becomes 500px.
- At **300 DPI**: 1 point = ~4.17 pixels. A 500pt-wide crop becomes ~2,083px.
- At **400 DPI**: 1 point = ~5.56 pixels. Same crop becomes ~2,778px.

Higher DPI = more detail = better OCR accuracy, but slower rendering and larger images.

## The `.to_image()` → `.original` pattern

This is the complete pattern we use to extract a chart image for OCR:

```python
# 1. Find the chart image on the page
chart_img = None
for img in page.images:
    if img["top"] > 300 and img["width"] > 200:  # filter by position and size
        chart_img = img
        break

# 2. Crop the page to the image's bounding box
bbox = (chart_img["x0"], chart_img["top"],
        chart_img["x0"] + chart_img["width"],
        chart_img["top"] + chart_img["height"])
cropped = page.crop(bbox)

# 3. Render the crop as a PIL Image at high DPI
pil_img = cropped.to_image(resolution=400).original

# 4. pil_img is now a PIL.Image.Image — ready for preprocessing and OCR
pil_img = pil_img.convert("L")  # grayscale
```

**Why this indirect approach?** pdfplumber doesn't give you the raw embedded bitmap. Instead, it re-renders the page region as a new image. The result is visually identical to the embedded chart, but it's a fresh render at whatever DPI you choose. This is actually better for OCR — we can render at higher DPI than the original image was embedded at.

## Merged cells and the newline trick

When pdfplumber encounters a **merged cell** (a table cell that spans multiple visual rows), it concatenates all the text content with `\n` (newline) separators:

```python
# Old-format fixed income table extracts as a single row with merged cells:
table = [
    ['Indexador', 'Taxa média', 'Valor', 'Percentual'],       # header
    ['%CDI\nPRE\nIPCA+\nSELIC+', '118,43%\n13,09%\n7,32%\n0,10%',
     'R$ 62.504,12\nR$ 54.605,97\nR$ 44.836,34\nR$ 468.576,88',
     '9,91%\n8,66%\n7,11%\n74,32%']                           # merged data row
]
```

What looks like a 4-row table in the PDF becomes a 2-row table in pdfplumber's output — one header row, one data row with newlines inside each cell.

**Detection strategy:** Check if a cell contains `\n`. If it does, split all cells by `\n` and iterate them in parallel:

```python
if "\n" in row[0]:
    indexers = row[0].split("\n")      # ['%CDI', 'PRE', 'IPCA+', 'SELIC+']
    rates = row[1].split("\n")          # ['118,43%', '13,09%', '7,32%', '0,10%']
    values = row[2].split("\n")         # ['R$ 62.504,12', 'R$ 54.605,97', ...]
    pcts = row[3].split("\n")           # ['9,91%', '8,66%', ...]

    for i, indexer in enumerate(indexers):
        # rates[i], values[i], pcts[i] correspond to this indexer
        process(indexer, rates[i], values[i], pcts[i])
```

**Key assumption:** All cells in a merged row have the same number of `\n`-separated values, in the same order. This holds true for our PDFs.

This is how `_parse_fixed_income_page()` handles the old PDF format. The key insight: **newlines inside a cell = merged rows**.

## Images in PDFs — deeper explanation

PDF files can contain two types of visual content:

1. **Vector content** — text characters, lines, shapes, drawn using PDF drawing operators. This is what pdfplumber extracts natively.
2. **Raster content** — pixel images (like photos, charts, logos) embedded as bitmap data (similar to PNG/JPEG). pdfplumber can tell you where they are, but can't read the pixels directly.

In our AUVP reports:
- The summary tables, portfolio tables, stock/FII tables → **vector** (extractable text)
- The proventos bar chart, allocation donut charts, sector distribution charts → **raster images** (need OCR)
- The AUVP logo in the header → **raster image** (we ignore it)

When you call `page.images`, you get metadata about every raster image:

```python
images = page.images
# [
#   {'x0': 435, 'top': 2, 'width': 120, 'height': 46},   # logo (top-right)
#   {'x0': 48, 'top': 413, 'width': 499, 'height': 333},  # proventos chart
# ]
```

We filter images by position (`top > 300`) and size (`width > 200`) to find the proventos chart while ignoring the logo.

## Debugging tips

### When a table isn't extracting correctly

```python
# Visual debug — renders the page with colored overlays showing
# where pdfplumber detected lines, cells, and tables
img = page.to_image()
img.debug_tablefinder()      # draws red/blue rectangles over detected cells
img.save("debug_tables.png") # open this to see what pdfplumber "sees"
```

If the debug image shows no colored cells where you expect a table, the table likely has no visible border lines. Try changing `table_settings` to use `"text"` strategy.

### When text isn't where you expect

```python
# Print all words with their page coordinates
for w in page.extract_words():
    print(f"x={w['x0']:.0f} y={w['top']:.0f} '{w['text']}'")

# Output:
# x=48 y=85  'Movimentações'
# x=241 y=85  'Financeiras'
# x=48 y=146  'Ativos'
# x=101 y=146  'Adquiridos:'
# x=48 y=384  'Proventos:'
```

This shows you exactly where each word sits on the page, helping you understand the layout and set correct coordinates for cropping.

### When you need to see the raw characters

```python
# Even more granular: individual characters with font info
for c in page.chars:
    if c['top'] > 380 and c['top'] < 420:  # filter by region
        print(f"'{c['text']}' at ({c['x0']:.0f}, {c['top']:.0f}) font={c['fontname']}")
```

## Limitations

- **Cannot extract text from images** — if text is rendered as part of a raster image (like chart labels), pdfplumber sees nothing. There are zero characters in the image area. You need OCR (Tesseract) for this.
- **Table detection depends on visible lines** — tables must have drawn border lines for automatic detection. Tables styled only with background colors or spacing won't be found.
- **Merged cells** — pdfplumber extracts them as a single cell with newlines inside. You need to detect and split them (see above).
- **Scanned PDFs** — if the entire PDF is a scan (one big image per page), pdfplumber extracts nothing. You'd need to OCR every page. Our PDFs are digitally generated (text is real text, not scanned), so most content is extractable.
- **Fragile text reconstruction** — `extract_text()` groups characters by y-coordinate into lines. If the PDF has unusual spacing, overlapping elements, or non-standard character positioning, the reconstructed text can be garbled or have unexpected spaces. Our parser relies on regex over extracted text, which works because AUVP reports use clean, consistent layouts.
- **Slow for large PDFs** — pdfplumber processes every object on every page. For a 10-page PDF it's fast (< 1 second). For a 1000-page PDF, consider processing only the pages you need.
