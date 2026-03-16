# Tesseract OCR — Extracting Text from Images

> Docs: https://github.com/tesseract-ocr/tesseract
> Python wrapper: https://github.com/madmaze/pytesseract

## What it does

Tesseract is an open-source OCR (Optical Character Recognition) engine. It takes an image and returns the text it "reads" from it. In this project, we use it to extract proventos values from chart images embedded in the PDFs.

## Installation

```bash
# macOS
brew install tesseract

# Ubuntu/Debian (and Docker)
apt-get install tesseract-ocr

# Python wrapper
pip install pytesseract Pillow
```

Tesseract is a system binary — `pytesseract` is just a Python wrapper that calls it via subprocess.

## Basic usage

```python
from PIL import Image
import pytesseract

img = Image.open("chart.png")
text = pytesseract.image_to_string(img)
print(text)
# "@ Acdes: R$ 1.982,54  @ Fils: R$ 744,11 @ CuponsR-F.: R$ 3.380,02"
```

## How it works (simplified)

1. **Preprocessing** — Tesseract converts the image to binary (black/white), identifies connected components (blobs of pixels)
2. **Layout analysis** — Groups blobs into characters, words, lines, blocks
3. **Recognition** — Matches character shapes against trained models (neural network based in v4+)
4. **Post-processing** — Applies dictionary/language corrections

## Key parameters

### Language

```python
text = pytesseract.image_to_string(img, lang='por')  # Portuguese
text = pytesseract.image_to_string(img, lang='eng')  # English (default)
```

Portuguese language pack needs separate installation (`brew install tesseract-lang` or `apt-get install tesseract-ocr-por`). In this project we use the default English because our text is mostly numbers and short labels — English works fine and avoids the extra dependency.

### Page segmentation mode (PSM)

Controls how Tesseract analyzes the layout:

```python
# --psm 6: Assume a uniform block of text (good for tables)
# --psm 7: Treat image as a single line of text
# --psm 11: Sparse text — find as much text as possible, no order
text = pytesseract.image_to_string(img, config='--psm 6')
```

Default (PSM 3 — fully automatic) works for our charts.

## Image preprocessing for better accuracy

Raw chart images often have low contrast, colored backgrounds, or small text. Preprocessing dramatically improves accuracy.

### What we do in this project

```python
from PIL import ImageFilter

# 1. Convert to grayscale — removes color channel noise
#    Charts have colored bars/backgrounds. Tesseract works best on
#    high-contrast black-on-white. Grayscale eliminates color as a
#    variable, leaving only brightness differences.
pil_img = pil_img.convert("L")

# 2. Sharpen — emphasizes character edges
#    After grayscale, text may have soft edges (anti-aliasing).
#    Sharpening increases contrast between character pixels and
#    background, making it easier for Tesseract to find boundaries.
pil_img = pil_img.filter(ImageFilter.SHARPEN)
```

Both steps are complementary: grayscale simplifies the input, sharpen enhances the signal. Removing either one degrades accuracy on our charts.

### Resolution matters

The most impactful setting is the DPI when converting the PDF crop to an image:

```python
# pdfplumber's to_image() accepts resolution in DPI
pil_img = cropped.to_image(resolution=400).original
```

We tested 200, 300, 400, and 600 DPI:
- **200/300 DPI**: `R$ 1.98254` (comma dropped — wrong)
- **400 DPI**: `R$ 1.982,54` (correct)
- **600 DPI**: `R$ 1.98254` (comma dropped again — too much detail confuses it)

**400 DPI with grayscale + sharpen** was our sweet spot.

### Other preprocessing techniques (not used but good to know)

```python
# Binarization — force pure black/white
img = img.point(lambda x: 0 if x < 128 else 255, '1')

# Dilation/erosion — thicken or thin characters
from PIL import ImageFilter
img = img.filter(ImageFilter.MaxFilter(3))  # dilate
img = img.filter(ImageFilter.MinFilter(3))  # erode

# Resize — scale up small text
img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
```

## Common OCR mistakes we encountered

| Original | OCR output | Problem |
|---|---|---|
| `Ações` | `Acées`, `Acdes`, `AcGées`, `Ac6es` | Portuguese characters mangled |
| `FIIs` | `Fils`, `FIls` | Lowercase L vs uppercase I |
| `R$ 1.982,54` | `R$ 1.98254` | Comma dropped |
| `R$ 1.223,59` | `R$ 1.22359` | Same comma issue |
| `Cupons R.F.` | `CuponsR-F.`, `CuponsR.F.` | Spaces/dots rearranged |

**Strategy:** Write flexible regexes that handle multiple OCR variants rather than trying to get perfect OCR output. For example: `Ac[^\s:]*s` matches all variants of "Ações".

## Debugging OCR

When OCR gives wrong results:

```python
# Save the image to visually inspect what Tesseract sees
pil_img.save("/tmp/debug_ocr.png")

# Try different resolutions
for res in [200, 300, 400, 600]:
    img = cropped.to_image(resolution=res).original
    img = img.convert('L').filter(ImageFilter.SHARPEN)
    text = pytesseract.image_to_string(img)
    print(f"res={res}: {text.strip().split(chr(10))[0]}")

# Get character-level confidence
data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
for i, (text, conf) in enumerate(zip(data['text'], data['conf'])):
    if text.strip():
        print(f"'{text}' confidence={conf}")
```

## pytesseract is a thin wrapper

`pytesseract` doesn't do OCR itself — it calls the system `tesseract` binary via `subprocess`. This means:

- If `tesseract` isn't installed, `pytesseract` fails with a `TesseractNotFoundError`
- The Python package and the system binary are separate installations
- In Docker, you need `apt-get install tesseract-ocr` (system binary) AND `pip install pytesseract` (Python wrapper)
- Our code wraps the OCR call in `try/except` and returns empty string on failure — this makes the app work even without tesseract (you just lose proventos breakdown)

```python
# From _ocr_proventos_chart():
try:
    from PIL import ImageFilter
    import pytesseract
    ...
    return pytesseract.image_to_string(pil_img)
except ImportError:
    return ""   # pytesseract not installed
except Exception:
    return ""   # tesseract binary not found or other error
```

## Why English mode works (and where it doesn't)

We use the default English language model instead of Portuguese (`lang='por'`). This avoids requiring the Portuguese language pack installation. Trade-off:

- **Numbers are fine** — `R$ 1.982,54` is recognized correctly regardless of language
- **Accented characters are mangled** — `Ações` becomes `Acées`, `Acdes`, `AcGées`
- **Strategy:** We accept the mangled text and write flexible regexes to match all variants: `Ac[^\s:]*s` matches any OCR variant of "Ações"

If you install the Portuguese pack (`brew install tesseract-lang` / `apt-get install tesseract-ocr-por`), you can use `lang='por'` for better character accuracy. But the regex approach is more robust since OCR will still make mistakes occasionally.

## Limitations

- **Accuracy is never 100%** — even with preprocessing, expect OCR errors. Design your parsing to tolerate mistakes.
- **Performance** — OCR is the slowest part of our pipeline (~1-2 seconds per chart). For 7 PDFs it's fine; for 100+ you'd want to parallelize or cache.
- **Fonts matter** — stylized, thin, or very small fonts reduce accuracy. The AUVP charts use clean sans-serif fonts which helps.
- **Language packs** — without the Portuguese pack, accented characters are unreliable. We work around this with flexible regexes.
