# Tesseract OCR — Extracting Text from Images

> Docs: https://github.com/tesseract-ocr/tesseract
> Python wrapper: https://github.com/madmaze/pytesseract

## What is OCR?

**OCR** stands for **Optical Character Recognition** — the technology that "reads" text from images. Think of it as the digital equivalent of a human looking at a photo of a document and typing out what they see.

When a PDF contains a chart (like our proventos bar chart), the labels inside that chart (e.g., "Ações: R$ 1.119,74") are not text — they're pixels baked into an image. Normal text extraction tools (like pdfplumber) can't read them. OCR is the bridge: it analyzes the pixel patterns and attempts to reconstruct the text.

## What is Tesseract?

**Tesseract** is an open-source OCR engine, originally developed by HP in the 1980s and now maintained by Google. It's one of the most widely used OCR engines in the world. As of version 4+ (2018), it uses an **LSTM neural network** (a type of deep learning model specialized for sequences) for character recognition, which significantly improved accuracy over the older pattern-matching approach.

Tesseract is a **command-line program** (a system binary), not a Python library. You install it separately on your operating system:

```bash
# macOS (via Homebrew, the macOS package manager)
brew install tesseract

# Ubuntu/Debian Linux (and inside Docker containers)
apt-get install tesseract-ocr
```

After installation, you can use it directly from the terminal:

```bash
tesseract image.png output_text
# Creates output_text.txt with the recognized text
```

## What is pytesseract?

**pytesseract** is a thin Python wrapper around the Tesseract binary. It doesn't do OCR itself — it saves your image to a temporary file, calls the `tesseract` command via `subprocess` (Python's way of running external programs), reads the output, and returns it as a Python string.

```bash
# Install the Python wrapper (and Pillow for image handling)
pip install pytesseract Pillow
```

**Important:** Installing `pytesseract` alone is NOT enough. You need both:
1. The system binary (`tesseract`) — does the actual OCR
2. The Python package (`pytesseract`) — calls the binary from Python

If `tesseract` isn't installed on the system, `pytesseract` raises a `TesseractNotFoundError`.

## What is Pillow (PIL)?

**Pillow** is Python's main image processing library (the modern fork of the older **PIL** — Python Imaging Library). We use it to:
- Open and manipulate images (`Image.open()`, `.convert()`, `.filter()`)
- Pass images to pytesseract for OCR

In imports you'll see `from PIL import Image` — this is Pillow, using the old `PIL` namespace for backwards compatibility.

## Basic usage

```python
from PIL import Image
import pytesseract

# Open an image file
img = Image.open("chart.png")

# Run OCR — returns a string with the recognized text
text = pytesseract.image_to_string(img)
print(text)
# "@ Acdes: R$ 1.982,54  @ Fils: R$ 744,11 @ CuponsR-F.: R$ 3.380,02"
```

That's the entire API for basic usage. The complexity comes from making the output accurate.

## How Tesseract works (simplified)

When you call `image_to_string()`, Tesseract performs these steps internally:

1. **Binarization** — Converts the image to pure black and white. Every pixel becomes either 0 (black) or 255 (white). This simplifies the input by removing gradients, colors, and shading. Tesseract uses **Otsu's method** (an algorithm that automatically finds the best threshold to separate foreground from background).

2. **Connected component analysis** — Finds "blobs" of connected black pixels. Each blob is a candidate character. For example, the letter "O" is one blob, "i" is two blobs (the dot and the stem).

3. **Layout analysis** — Groups blobs into characters → words → lines → blocks, based on spacing and alignment. This is where **Page Segmentation Mode (PSM)** comes in (explained below).

4. **Character recognition** — Each character-sized blob is fed into an **LSTM neural network** (Long Short-Term Memory — a type of recurrent neural network good at processing sequences). The network outputs probabilities for each possible character. For example: "this blob is 95% likely to be 'A', 3% likely to be '4', 2% likely to be 'H'".

5. **Word/dictionary correction** — Tesseract checks recognized words against a built-in dictionary for the selected language and may correct low-confidence characters. For example, if it reads "helo", it might correct to "hello".

## Key parameters

### Language model

Tesseract ships with language-specific models that affect both character recognition and dictionary correction:

```python
text = pytesseract.image_to_string(img, lang='eng')  # English (default)
text = pytesseract.image_to_string(img, lang='por')  # Portuguese
```

Each language model is a **trained data file** (`.traineddata`) stored in Tesseract's data directory. The English model is always installed. Others need separate installation:

```bash
# macOS — installs ALL language packs
brew install tesseract-lang

# Ubuntu — install just Portuguese
apt-get install tesseract-ocr-por
```

**In this project**, we use the default English model. Why? See the "Why English mode works" section below.

### Page Segmentation Mode (PSM)

**Page segmentation** is how Tesseract decides the structure of text on the page — is it a single column? Multiple columns? A single line? A table?

```python
# Pass PSM via the config parameter:
text = pytesseract.image_to_string(img, config='--psm 6')
```

The most useful modes:

| PSM | Description | When to use |
|-----|-------------|-------------|
| 3 | Fully automatic (default) | General purpose, works for most cases |
| 6 | Assume a uniform block of text | Tables, forms, structured layouts |
| 7 | Treat as a single line of text | When you know there's exactly one line |
| 11 | Sparse text, no particular order | Labels scattered across an image |
| 13 | Raw line, no dictionary | When dictionary correction hurts (e.g., codes, IDs) |

**In this project**, the default PSM 3 works for our charts — the legend text is organized in a readable left-to-right layout.

## Image preprocessing for better accuracy

OCR accuracy depends heavily on image quality. Raw chart images often have colored backgrounds, low contrast text, or small font sizes. **Preprocessing** the image before sending it to Tesseract can dramatically improve results.

### What we do in this project

```python
from PIL import ImageFilter

# 1. Convert to grayscale
#    Original chart has colored bars (dark green), colored text, colored background.
#    Tesseract's binarization works best when the input is already grayscale.
#    .convert("L") converts RGB (3 channels: red, green, blue) to grayscale
#    (1 channel: brightness), where L stands for "luminance".
pil_img = pil_img.convert("L")

# 2. Sharpen
#    Text in charts is often anti-aliased — the edges of characters have
#    semi-transparent pixels that blend with the background, making text
#    look smooth on screen but fuzzy for OCR. Sharpening increases the
#    contrast at edges (a technique called "unsharp masking"), making
#    character boundaries crisper and easier for Tesseract to detect.
pil_img = pil_img.filter(ImageFilter.SHARPEN)
```

**Anti-aliasing** is a rendering technique that smooths the edges of text and shapes by blending boundary pixels with the background color. It makes text look better on screen but creates "fuzzy" edges that confuse OCR. Sharpening counteracts this.

Both steps are complementary: grayscale simplifies the input (from 3 color channels to 1), sharpen enhances the signal (character edges). Removing either one degrades accuracy on our charts.

### Resolution (DPI) matters most

**DPI** (Dots Per Inch) controls how many pixels are generated per inch of the PDF page. When we convert a PDF crop to an image, higher DPI = more pixels = more detail for OCR to work with.

```python
# pdfplumber's to_image() accepts resolution in DPI
pil_img = cropped.to_image(resolution=400).original
```

At 300 DPI, a 500-point-wide chart becomes ~2,083 pixels wide. At 400 DPI, it's ~2,778 pixels wide — 33% more detail.

We tested 200, 300, 400, and 600 DPI on the December 2025 proventos chart:
- **200 DPI**: `R$ 1.98254` (comma dropped — wrong)
- **300 DPI**: `R$ 1.98254` (comma dropped — wrong)
- **400 DPI**: `R$ 1.982,54` (correct!)
- **600 DPI**: `R$ 1.98254` (comma dropped again)

Why does 600 DPI fail? More pixels means more detail in the anti-aliasing edges, which can create artifacts that confuse the character segmentation. There's a sweet spot — for our charts, **400 DPI with grayscale + sharpen** is optimal.

### Other preprocessing techniques (not used but good to know)

```python
# Binarization — force pure black/white manually
# Each pixel: if brightness < 128, make it black (0); otherwise white (255)
# The '1' mode means 1-bit (binary) image
img = img.point(lambda x: 0 if x < 128 else 255, '1')

# Dilation — thicken characters (useful for thin fonts that break apart)
# MaxFilter replaces each pixel with the maximum in a 3x3 neighborhood,
# effectively expanding bright (white) areas
from PIL import ImageFilter
img = img.filter(ImageFilter.MaxFilter(3))

# Erosion — thin characters (useful when characters merge together)
# MinFilter replaces each pixel with the minimum in a 3x3 neighborhood,
# effectively expanding dark (black) areas
img = img.filter(ImageFilter.MinFilter(3))

# Resize — scale up small text (Tesseract struggles with text below ~20px height)
# LANCZOS is a high-quality downsampling/upsampling filter
img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
```

## Common OCR mistakes we encountered

| Original text | OCR output | Problem |
|---|---|---|
| `Ações` | `Acées`, `Acdes`, `AcGées`, `Ac6es` | Portuguese characters (ç, õ) have no match in English model — Tesseract guesses wrong |
| `FIIs` | `Fils`, `FIls` | Lowercase `l` looks identical to uppercase `I` in many fonts |
| `R$ 1.982,54` | `R$ 1.98254` | The comma (`,`) is small and close to the digits — Tesseract misses it |
| `R$ 1.223,59` | `R$ 1.22359` | Same comma issue — consistent across similar number formats |
| `Cupons R.F.` | `CuponsR-F.`, `CuponsR.F.` | Spaces between words dropped; periods and dashes confused |

**Our strategy:** Don't try to get perfect OCR output. Instead, **write flexible regular expressions** (regex) that handle multiple OCR variants:

```python
# Instead of matching exactly "Ações":
r"Ações:?\s*R\$"          # would miss "Acdes", "Acées", etc.

# Match ANY OCR variant:
r"Ac[^\s:]*s:?\s*R\$"     # Ac + any non-space/colon chars + s
                           # matches: Ações, Acées, Acdes, AcGées, Ac6es
```

The regex `[^\s:]*` means "zero or more characters that are NOT a space or colon" — this catches whatever garbled characters OCR produces between "Ac" and "s".

## pytesseract architecture

Understanding the architecture helps when debugging:

```
Your Python code
    ↓ calls
pytesseract.image_to_string(img)
    ↓ internally:
    1. Saves PIL Image to a temporary .png file
    2. Builds command: "tesseract /tmp/xxx.png /tmp/xxx -l eng --psm 3"
    3. Runs command via subprocess.Popen()
    4. Reads /tmp/xxx.txt (Tesseract's output file)
    5. Returns the text as a Python string
    6. Cleans up temporary files
    ↓
"@ Acdes: R$ 1.982,54 ..."
```

This means:
- Every `image_to_string()` call involves file I/O and a subprocess — it's not instant (~0.5-2 seconds per image)
- If `tesseract` isn't on the system PATH, pytesseract can't find it
- Error messages come from the `tesseract` binary, not from Python

Our code wraps this in `try/except` to gracefully handle missing installations:

```python
# From _ocr_proventos_chart() in parser.py:
try:
    from PIL import ImageFilter
    import pytesseract
    ...
    return pytesseract.image_to_string(pil_img)
except ImportError:
    return ""   # pytesseract package not installed
except Exception:
    return ""   # tesseract binary not found, or image processing error
```

This makes the app work even without tesseract — you just lose the proventos breakdown (it shows 0 for ações/FIIs/cupons).

## Debugging OCR

When OCR gives wrong results, here's how to investigate:

### Step 1: Look at what Tesseract sees

```python
# Save the preprocessed image — open it and check if text is legible to YOU
pil_img.save("/tmp/debug_ocr.png")
# If YOU can't read it, Tesseract can't either
```

### Step 2: Try different resolutions

```python
from PIL import ImageFilter

for res in [200, 300, 400, 600]:
    img = cropped.to_image(resolution=res).original
    img = img.convert('L').filter(ImageFilter.SHARPEN)
    text = pytesseract.image_to_string(img)
    first_line = text.strip().split('\n')[0]
    print(f"res={res}: {first_line}")
```

### Step 3: Check per-character confidence

Tesseract can report how confident it is about each recognized character (0-100):

```python
# image_to_data returns a dict with parallel arrays
data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

for text, conf in zip(data['text'], data['conf']):
    if text.strip():
        # conf is 0-100, where 100 = very confident
        # Characters below ~60 are likely wrong
        print(f"'{text}' confidence={conf}")
```

This helps identify which specific characters are being misread. We don't use this in production (we rely on regex flexibility instead), but it's valuable for debugging new PDF formats.

## Why English mode works (and where it doesn't)

We use the default English language model instead of Portuguese (`lang='por'`). This avoids requiring the Portuguese language pack installation. The trade-off:

- **Numbers are fine** — digits (0-9), dots, commas, and the `R$` symbol are recognized correctly regardless of language model. Numbers look the same in every language.
- **Accented characters are mangled** — the English model has no training data for `ç`, `ã`, `õ`, `é`. It guesses the closest ASCII characters, producing variants like `Acées` for `Ações`.
- **Our strategy:** Accept the mangled text and write flexible regexes that match all variants: `Ac[^\s:]*s` matches any OCR variant of "Ações". This is actually more robust than relying on perfect Portuguese OCR, because even with the Portuguese model, OCR still makes occasional mistakes.

If you want to try the Portuguese model:

```bash
# Install the language pack
brew install tesseract-lang          # macOS (installs all languages)
apt-get install tesseract-ocr-por    # Ubuntu (just Portuguese)
```

```python
text = pytesseract.image_to_string(img, lang='por')
```

## Limitations

- **Accuracy is never 100%** — even with perfect preprocessing, OCR will make mistakes. Design your parsing code to tolerate errors (flexible regexes, sanity checks on parsed values).
- **Performance** — OCR is the slowest part of our pipeline (~1-2 seconds per chart image). For our 7 PDFs that's fine (~10 seconds total). For 100+ PDFs you'd want to parallelize (e.g., `concurrent.futures.ThreadPoolExecutor`) or cache results.
- **Fonts matter** — stylized fonts, very thin fonts, or text smaller than ~20 pixels tall significantly reduce accuracy. The AUVP charts use clean sans-serif fonts (like Montserrat) which helps.
- **Background interference** — colored backgrounds, grid lines, overlapping chart elements can confuse character detection. Our grayscale + sharpen preprocessing mitigates this.
- **Language packs** — without the Portuguese pack, accented characters are unreliable. We work around this with flexible regexes rather than requiring the pack.
