# Brazilian Number Parsing — R$ 1.234,56

## The format

Brazil uses the opposite convention from the US:
- **Dot** (`.`) = thousand separator: `1.234.567`
- **Comma** (`,`) = decimal separator: `1.234,56`
- **Currency prefix:** `R$` (Real) with a space: `R$ 1.234,56`
- **Negative:** prefix with `-`: `-R$ 4.316,47`
- **Percentage:** comma decimal + `%`: `4,40%`

## The conversion

```
Brazilian       →  Float
R$ 1.234,56     →  1234.56
R$ 45.280,50    →  45280.50
-R$ 4.316,47    →  -4316.47
4,40%           →  4.40
```

### Algorithm in `parse_br_number()`

```python
def parse_br_number(text: str) -> float:
    text = text.strip()
    text = re.sub(r"R\$\s*", "", text)     # remove R$ prefix
    negative = text.startswith("-")
    if negative:
        text = text[1:].strip()
    text = text.replace(" ", "")            # remove PDF extraction spaces
    # Handle OCR-dropped comma: "1.98254" → "1.982,54"
    if "," not in text and re.match(r"^\d+\.\d{4,}$", text):
        text = text[:-2] + "," + text[-2:]
    text = text.replace(".", "")            # remove thousand dots
    text = text.replace(",", ".")           # decimal comma → dot
    return -float(text) if negative else float(text)
```

**The order of transformations matters.** Here's the complete pipeline:

```
Input: "R$ 1.243.581,34"
  1. Strip + remove "R$"    → "1.243.581,34"
  2. Detect negative (-)    → not negative
  3. Remove ALL spaces      → "1.243.581,34"   (handles PDF artifacts like "1  243  581,34")
  4. OCR comma-drop check   → has comma, skip  (only fires when no comma + dot + 4+ digits)
  5. Remove dots (thousands)→ "1243581,34"
  6. Comma → dot (decimal)  → "1243581.34"
  7. float()                → 1243581.34
```

**Why step 4 must come before step 5:** The OCR fix pattern looks for `\d+\.\d{4,}` (dot followed by 4+ digits). If we removed dots first, the pattern would never match.

Step by step for a negative value `-R$ 4.316,47`:
1. Strip + remove `R$` → `-4.316,47`
2. Detect `-`, strip it → `4.316,47`, remember negative=True
3. Remove spaces → `4.316,47`
4. OCR check → has comma, skip
5. Remove dots → `4316,47`
6. Comma to dot → `4316.47`
7. float() → 4316.47
8. Apply negative → -4316.47

### Algorithm in `parse_br_percentage()`

```python
def parse_br_percentage(text: str) -> float:
    text = text.strip().replace("%", "")
    text = re.sub(r"\s+", ".", text)  # spaces → dot (PDF artifact)
    text = text.replace(",", ".")
    return float(text)
```

Step by step for `9  74%` (PDF-extracted):
1. Remove `%` → `9  74`
2. Spaces → dot → `9.74`
3. `float()` → `9.74`

**Why not just strip spaces?** Because `9  74` would become `974` (wrong). The spaces replace the decimal dot in percentages, while in currency values, spaces replace the thousand-separator dot. Different semantics, different handling.

## The OCR comma problem

Tesseract sometimes drops commas from numbers:

| PDF shows | OCR reads | Naive parse | Correct |
|---|---|---|---|
| `R$ 1.982,54` | `R$ 1.98254` | 198254.0 | 1982.54 |
| `R$ 1.223,59` | `R$ 1.22359` | 122359.0 | 1223.59 |

Detection: if there's no comma AND we see `\d+\.\d{4,}` (dot followed by 4+ digits), the comma was dropped. We insert it before the last 2 digits:

```python
if "," not in text and re.match(r"^\d+\.\d{4,}$", text):
    text = text[:-2] + "," + text[-2:]
# "1.98254" → "1.982,54" → then normal parsing → 1982.54
```

**Why 4+ digits is the right threshold:** In Brazilian format, the dot is always a thousand separator (3 digits after it: `1.234`). If we see 4+ digits after the dot (`1.98254`), it's impossible in legitimate BR format — the comma must have been dropped. This is safe because AUVP PDFs always use comma for decimals and dot for thousands.

## Regex patterns for Brazilian values

```python
# Match R$ value in text
r"R\$\s*([\d\s.,]+)"          # captures "1.243.581,34" or "45  280,50"

# Match percentage
r"(\d[\d\s,]+%)"              # captures "4,40%" or "9  74%"

# Match negative R$ value
r"(-?)R\$\s*([\d\s.,]+)"      # group(1) is "-" or "", group(2) is the number
```
