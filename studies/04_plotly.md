# Plotly — Interactive Charts

> Docs: https://plotly.com/python/
> Express API: https://plotly.com/python/plotly-express/
> Graph Objects API: https://plotly.com/python/graph-objects/

## What is Plotly?

**Plotly** is a charting library that creates **interactive** charts — you can zoom, pan, hover to see values, click legend items to toggle series on/off, and export as PNG. Unlike matplotlib (which renders static images), Plotly renders charts in the browser using JavaScript.

**How it works under the hood:**

1. Your Python code builds a chart description (a nested dict/JSON structure called a **figure**)
2. The figure is serialized to JSON
3. In the browser, **Plotly.js** (a JavaScript library) reads the JSON and renders the chart as an interactive SVG/WebGL element

You never write JavaScript — Python generates the JSON spec, and the browser does the rendering. This is why Plotly charts are interactive even though you wrote only Python.

## The Figure object

Everything in Plotly revolves around the **Figure**. A figure has two main parts:

```python
fig = {
    "data": [...],      # list of "traces" (lines, bars, pie slices)
    "layout": {...}     # axes, title, legend, margins, colors
}
```

A **trace** is a single data series on the chart — one line, one set of bars, one pie. You can have multiple traces on one figure (e.g., a line chart with two lines).

The **layout** controls everything that's not data — axis labels, tick formats, margins, legend position, title.

## Two APIs: Express vs Graph Objects

Plotly offers two ways to build figures. We use both in this project.

### Plotly Express (`px`) — quick charts from DataFrames

**Plotly Express** is the high-level API. You pass a **pandas DataFrame** and column names, and it builds the entire figure in one call:

```python
import plotly.express as px
import pandas as pd

df = pd.DataFrame({
    "Mês": ["2025-08", "2025-09", "2025-10"],
    "Rentabilidade (%)": [2.0, 1.67, 0.87],
})

fig = px.bar(df, x="Mês", y="Rentabilidade (%)")
```

That's a complete bar chart. Express handles trace creation, axis labels, colors, and legend automatically. Under the hood, it creates a `Figure` object with the right traces and layout.

**When to use Express:**
- Simple charts with data already in a DataFrame
- One data series, or stacked/grouped variants of one chart type
- When you want something quick and don't need fine control

### Graph Objects (`go`) — full control

**Graph Objects** is the low-level API. You create an empty `Figure` and add traces manually:

```python
import plotly.graph_objects as go

fig = go.Figure()

# Each add_xxx() creates one trace
fig.add_scatter(
    x=["2025-08", "2025-09", "2025-10"],
    y=[902824, 1085300, 1139674],
    mode="lines+markers",         # what to draw: lines, dots, or both
    name="Patrimônio",            # label in the legend
    line=dict(color="#2ecc71", width=3),
)

fig.add_bar(
    x=["2025-08", "2025-09", "2025-10"],
    y=[5000, 6000, 7000],
    name="Aporte",
    marker_color="#FF6B6B",
)
```

**When to use Graph Objects:**
- Multiple different trace types on one chart (e.g., bars + line)
- Dual Y-axes
- Custom hover templates
- Fine control over individual trace appearance

### Mixing both

You can start with Express and then modify the result:

```python
fig = px.bar(df, x="Mês", y="Value")        # Express creates the base
fig.add_scatter(x=df["Mês"], y=df["Total"],  # add a line trace via Graph Objects
                mode="lines+markers", name="Total")
fig.update_layout(yaxis_title="R$")           # customize layout
```

We do this for the proventos chart — Express creates the stacked bars, then we add a total line with Graph Objects.

## Chart types used in this project

### Donut chart (allocation, fixed income, sectors)

A **donut chart** is a pie chart with a hole in the center:

```python
fig = px.pie(df, names="Classe", values="Valor", hole=0.4)
fig.update_traces(textinfo="label+percent", textposition="outside")
```

- `names` — column with category labels (e.g., "Renda Fixa", "Ações")
- `values` — column with numeric values (determines slice size)
- `hole=0.4` — the inner hole radius as a fraction (0 = full pie, 1 = no pie). 0.4 is a common donut ratio.
- `textinfo="label+percent"` — show both the category name and percentage on each slice
- `textposition="outside"` — place labels outside the slices. This prevents labels from overlapping on small slices. The alternative `"inside"` places them on the slice itself (hard to read for thin slices).

### Bar chart (monthly returns)

```python
fig = px.bar(df, x="Mês", y="Rentabilidade (%)")
```

Simple one-series bar chart. Plotly auto-assigns a blue color.

### Stacked bar chart (proventos breakdown)

```python
fig = px.bar(
    df, x="Mês",
    y=["Ações", "FIIs", "Cupons RF"],   # multiple columns = stacked segments
    barmode="stack",                      # stack them (default is "group")
)
```

When you pass a **list of column names** to `y`, Plotly creates one trace per column. `barmode="stack"` stacks them vertically. Without `barmode="stack"`, they'd be side-by-side (`"group"`).

**Color assignment:** Plotly auto-assigns colors from its default palette. The colors are consistent per column name across re-renders — "Ações" will always be the same color. You don't need to specify colors manually unless you want specific ones.

### Grouped bar chart (allocation vs target)

```python
fig = go.Figure()
fig.add_trace(go.Bar(name="Atual", x=classes, y=current_values,
                     text=[f"{v:.1f}%" for v in current_values],
                     textposition="auto"))
fig.add_trace(go.Bar(name="Meta", x=classes, y=target_values,
                     text=[f"{v:.1f}%" for v in target_values],
                     textposition="auto"))
fig.update_layout(barmode="group")
```

Two `go.Bar` traces with `barmode="group"` places them side-by-side at each x position. `textposition="auto"` lets Plotly decide whether to place labels inside or outside based on bar height.

### Dual Y-axis chart (aportes: bars + cumulative line)

This is the most complex chart in the project. It shows monthly aportes as bars (left Y-axis) and cumulative total as a line (right Y-axis):

```python
fig = go.Figure()

# Bars — use the default Y-axis (y, on the left)
fig.add_bar(
    x=df["Mês"], y=df["Aporte no Mês"],
    name="Aporte no Mês",
    marker_color="#FF6B6B",
)

# Line — bind to the second Y-axis (y2, on the right)
fig.add_scatter(
    x=df["Mês"], y=df["Acumulado"],
    name="Acumulado",
    yaxis="y2",                              # THIS is the key — assigns to right axis
    line=dict(color="#2ecc71", width=2),
)

# Configure both Y-axes
fig.update_layout(
    yaxis=dict(title="Mensal", tickprefix="R$ "),         # left axis
    yaxis2=dict(                                           # right axis
        title="Acumulado",
        tickprefix="R$ ",
        overlaying="y",    # overlay on top of the first y-axis (share same plot area)
        side="right",      # place tick labels on the right
    ),
)
```

**How dual axes work:**
- Every trace has an implicit `yaxis="y"` (the default/left axis) unless you specify `yaxis="y2"`
- `yaxis2` in the layout defines the second axis. `overlaying="y"` means it shares the same plot area as the first axis (not a separate subplot). `side="right"` puts the tick labels on the right.
- The two axes scale independently — bars might go up to R$ 13,000 while the cumulative line goes up to R$ 200,000. Each axis auto-scales to its own data range.

## Traces and the `mode` parameter

**Scatter traces** (`add_scatter()`) can render in different modes:

| Mode | What it draws |
|------|---------------|
| `"lines"` | Connected line only |
| `"markers"` | Dots only |
| `"lines+markers"` | Line with dots at each data point |
| `"lines+markers+text"` | Line with dots AND text labels at each point |
| `"text"` | Only text labels, no line or dots |

```python
# Line with dots, values shown on hover only (mobile-friendly)
fig.add_scatter(mode="lines+markers", hovertemplate="%{text}")

# Line with dots AND text labels (desktop, when space permits)
fig.add_scatter(mode="lines+markers+text", text=[...], textposition="top center")
```

**Mobile consideration:** `"lines+markers+text"` renders text labels at every data point. On small screens (iPhone), these labels overlap and become unreadable. That's why our responsive version uses `"lines+markers"` with values only in hover tooltips.

## Hover templates

**Hover templates** control what appears when the user hovers over (or taps on mobile) a data point:

```python
fig.add_scatter(
    x=df["Mês"], y=df["Patrimônio"],
    hovertemplate="%{x}<br>%{text}<extra></extra>",
    text=[format_brl(v) for v in df["Patrimônio"]],
)
```

Template syntax:
- `%{x}` — the x value of the data point (e.g., "2026-01")
- `%{y}` — the y value (e.g., 1243581.34 — raw number, not formatted)
- `%{text}` — value from the `text` array you provide (e.g., "R$ 1.243.581,34")
- `<br>` — HTML line break in the tooltip
- `<extra></extra>` — hides the **trace name** from the tooltip (by default, Plotly shows the trace name in a colored box next to the tooltip — this removes it for a cleaner look)

**Why we use `%{text}` instead of `%{y}`:** The `y` value is a raw float (1243581.34), which Plotly would format with its own rules. By passing pre-formatted strings in `text`, we get exact Brazilian currency formatting ("R$ 1.243.581,34").

**Important:** `%{text}` requires you to pass a `text=` array to the same trace. Without it, `%{text}` renders as empty.

## Layout customization

The **layout** controls everything that isn't data:

```python
fig.update_layout(
    # Title
    title="Aportes Mensais (BTG Pactual)",

    # Y-axis
    yaxis_title="R$",                    # axis label
    yaxis_tickprefix="R$ ",              # prefix before each tick value
    yaxis_tickformat=",.",               # number format (comma = thousands, dot = decimal)

    # Margins — in pixels, controls whitespace around the chart
    margin=dict(l=10, r=10, t=40, b=10),  # left, right, top, bottom

    # Legend
    legend=dict(
        orientation="h",          # "h" = horizontal (items side by side)
                                  # "v" = vertical (default, items stacked)
        y=-0.2,                   # position below the chart (negative = below)
        x=0.5,                    # horizontal center
        xanchor="center",        # anchor point for x positioning
    ),

    # Font — affects all text in the chart
    font=dict(size=11),

    # Bar mode — how multiple bar traces are arranged
    barmode="stack",    # "stack" = stacked on top of each other
                        # "group" = side by side
                        # "overlay" = on top of each other with transparency
)
```

### Shorthand vs dict syntax

Plotly accepts both:

```python
# These are equivalent:
fig.update_layout(yaxis_title="R$", yaxis_tickprefix="R$ ")
fig.update_layout(yaxis=dict(title="R$", tickprefix="R$ "))
```

The underscore syntax (`yaxis_title`) is flattened shorthand. The dict syntax is more readable for complex configurations.

## Colors

### Specifying colors

```python
# Named CSS colors (140+ options)
line=dict(color="white")
line=dict(color="red")
line=dict(color="steelblue")

# Hex colors (most precise)
marker_color="#FF6B6B"    # salmon red (our aportes color)
marker_color="#2ecc71"    # green (our patrimônio color)
marker_color="#3498db"    # blue (our rentabilidade color)

# RGB/RGBA
marker_color="rgb(255, 107, 107)"
marker_color="rgba(255, 107, 107, 0.5)"   # 50% transparent
```

### Line styles

```python
line=dict(
    color="#2ecc71",
    width=3,           # line thickness in pixels
    dash="solid",      # line style: "solid", "dot", "dash", "dashdot", "longdash"
)
```

We use `dash="dot"` for the aportes cumulative line to visually distinguish it from the patrimônio line.

### Auto-assigned colors

When using Plotly Express with multiple series (like stacked bars), Plotly auto-assigns colors from its default **color sequence** — a carefully chosen palette where adjacent colors are visually distinct. The assignment is deterministic: same column name → same color every time.

## Text labels on charts

You can show values directly on the chart (not just on hover):

```python
fig.add_bar(
    x=df["Mês"], y=df["Value"],
    text=[format_brl(v) for v in df["Value"]],   # what to display
    textposition="outside",                        # where to place it
)
```

`textposition` options:
- `"inside"` — centered inside the bar (only works if bar is tall enough)
- `"outside"` — above the bar (may extend beyond the chart area)
- `"auto"` — Plotly decides based on available space
- `"none"` — don't show text (use hover only)

**When to use text vs. hover:**
- **Desktop with few data points** — text labels work well, no overlap
- **Mobile or many data points** — use hover only (`textposition="none"` or just don't pass `text`). Labels overlap and become unreadable.

Our responsive approach: remove `+text` from `mode`, keep `text` for `hovertemplate` to use:

```python
# Mobile-friendly: values on hover, not drawn on chart
fig.add_scatter(
    mode="lines+markers",                          # no "+text"
    hovertemplate="%{x}<br>%{text}<extra></extra>", # values in tooltip
    text=[format_brl(v) for v in values],           # data for hover
)
```

## Plotly + Streamlit integration

Streamlit has built-in Plotly support:

```python
st.plotly_chart(fig, use_container_width=True)
```

- `use_container_width=True` — makes the chart fill its container's width. **Essential for responsive design.** Without it, Plotly renders at a fixed default width (~700px) which looks wrong on both wide monitors and phones.
- The chart is interactive: hover, zoom, pan, toggle legend items all work in the browser.

### Our responsive wrapper

We apply consistent mobile-friendly settings to every chart:

```python
def responsive_chart(fig, **kwargs):
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),   # minimal whitespace
        legend=dict(
            orientation="h",    # horizontal legend (stacks vertically on narrow screens)
            y=-0.2,             # below the chart
            x=0.5, xanchor="center",
        ),
        font=dict(size=11),     # slightly smaller than default (14)
    )
    st.plotly_chart(fig, use_container_width=True, **kwargs)
```

This is called for every chart instead of `st.plotly_chart()` directly. It ensures:
- Minimal margins (saves space on mobile)
- Horizontal legend below the chart (doesn't eat into chart width)
- Smaller font (fits more on small screens)

## How Plotly renders (the JSON pipeline)

Understanding this helps with debugging:

```
Python code
  ↓ builds
Figure object (Python dicts/lists)
  ↓ serialized to
JSON spec (~50KB for a typical chart)
  ↓ sent to browser via Streamlit's websocket
Plotly.js (JavaScript library in the browser)
  ↓ reads JSON, renders
Interactive SVG/WebGL in the browser DOM
```

You can inspect the JSON spec:

```python
import json
print(json.dumps(fig.to_dict(), indent=2)[:500])
# Shows the trace data and layout as a JSON structure
```

This means:
- **All data is sent to the browser** — for our small datasets this is fine, but for millions of points you'd want server-side aggregation
- **Interactivity is client-side** — hover, zoom, pan don't call back to Python. The browser handles it with JavaScript.
- **No Python needed after rendering** — if the Streamlit server goes down, charts already loaded in the browser still work (until you refresh)

## Performance notes

- Plotly charts are rendered **client-side** (in the browser via JavaScript). The Python code only generates the JSON spec.
- For large datasets (thousands of points), consider `fig.update_traces(marker=dict(size=3))` to reduce SVG element count, or use `plotly.graph_objects.Scattergl` (WebGL renderer) instead of `Scatter` (SVG renderer).
- Our data is small (7-20 data points per chart) so performance is not a concern.
- Each `st.plotly_chart()` call sends the full JSON spec to the browser. With 5-6 charts on a page, that's ~200-300KB total — negligible.
