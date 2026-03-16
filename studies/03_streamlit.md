# Streamlit — Building Data Dashboards in Python

> Docs: https://docs.streamlit.io
> API reference: https://docs.streamlit.io/develop/api-reference
> Gallery: https://streamlit.io/gallery

## What it does

Streamlit turns Python scripts into interactive web apps. You write Python top-to-bottom, call `st.` functions to render UI elements, and Streamlit handles the HTML/JS/CSS. No frontend code needed.

## Mental model — the re-run paradigm

**This is the single most important concept in Streamlit.** Everything else follows from it.

Streamlit re-runs your **entire script from top to bottom** on every user interaction (button click, dropdown change, slider move, etc.). This is fundamentally different from traditional web frameworks where you handle specific routes/events.

```python
import streamlit as st

st.title("Hello")
name = st.text_input("Name")   # renders an input box
st.write(f"Hello, {name}")     # re-runs when input changes
```

Every time the user types in the input, the entire script re-runs, `name` gets the new value, and the output updates.

**Implications for this project:**

1. **Auth must be at the top** — `check_auth()` is called before any other UI. On every re-run, it checks `session_state["authenticated"]`. If not authenticated, it calls `st.stop()` which halts the script — nothing below renders.

2. **Multi-page apps re-run independently** — when you navigate to `pages/detalhes.py`, that script runs from top to bottom (not `app.py`). That's why both files call `check_auth()` at the top.

3. **Variables reset** — local variables don't survive between re-runs. Only `st.session_state` persists.

4. **Expensive operations re-execute** — without `@st.cache_data`, every `load_all_reports()` call would read all JSON files from disk on every button click. Caching prevents this.

## Layout

### Page config (must be first Streamlit call)

```python
st.set_page_config(
    page_title="Tab title",     # browser tab
    page_icon="📊",             # favicon
    layout="wide",              # "centered" (default) or "wide"
)
```

### Columns

```python
col1, col2 = st.columns(2)          # equal width
col1, col2 = st.columns([2, 1])     # 2:1 ratio

with col1:
    st.metric("Value", "R$ 100")
with col2:
    st.metric("Change", "+5%")
```

**Mobile tip:** 4 columns look cramped on phones. We use 2 columns for metrics so they stack nicely on narrow screens.

### Sidebar

```python
st.sidebar.title("Controls")
month = st.sidebar.selectbox("Month", ["Jan", "Feb"])

# Or use 'with':
with st.sidebar:
    st.selectbox("Month", ["Jan", "Feb"])
```

On mobile, the sidebar becomes a hamburger menu.

### Expander

```python
with st.expander("Advanced settings"):
    st.number_input("Threshold", value=0.5)
```

Collapsed by default — great for secondary controls. We use it for the "Registrar Aporte" form in the sidebar.

## Display elements

### Metrics

```python
st.metric("Patrimônio", "R$ 1.243.581", delta="+4.4%")
# Shows label, value, and optional delta with green/red coloring
```

### DataFrames

```python
st.dataframe(df, hide_index=True, use_container_width=True)
# Interactive table with sorting, searching, resizing
```

### Charts (Plotly integration)

```python
import plotly.express as px

fig = px.bar(df, x="Month", y="Value")
st.plotly_chart(fig, use_container_width=True)
# use_container_width=True makes it responsive
```

### Text

```python
st.title("Big title")           # h1
st.header("Section")            # h2
st.subheader("Subsection")      # h3
st.write("Anything")            # smart — renders markdown, DataFrames, etc.
st.markdown("**bold** text")    # explicit markdown
st.info("Info message")         # blue box
st.warning("Warning")           # yellow box
st.error("Error")               # red box
st.success("Done!")             # green box
```

## Input widgets

### Selectbox

```python
month = st.selectbox(
    "Month",
    ["2025-01", "2025-02"],
    index=0,                              # default selection
    format_func=lambda m: f"{m[5:]}/{m[:4]}",  # display format
    key="unique_key",                     # required if same widget appears twice
)
# month == "2025-01" (the actual value), NOT "01/2025" (the display format)
```

**Important:** `format_func` only affects what the user sees in the dropdown. The returned value is always the original item from the list. In our app, `selected_month` is `"2026-01"` (which we slice as `[:7]`), not `"01/2026"`.

### Number input

```python
value = st.number_input(
    "Amount (R$)",
    value=0.0,
    min_value=0.0,
    step=100.0,
    format="%.2f",
)
```

### Button

```python
if st.button("Save"):
    # This block runs only when clicked
    save_data()
    st.rerun()  # force a re-run to refresh the UI
```

## State management

Since the script re-runs entirely on every interaction, local variables reset. `st.session_state` persists across re-runs:

```python
# Initialize
if "counter" not in st.session_state:
    st.session_state.counter = 0

# Use
if st.button("Increment"):
    st.session_state.counter += 1

st.write(f"Count: {st.session_state.counter}")
```

We use it for authentication:

```python
if st.session_state.get("authenticated"):
    return  # already logged in
```

## Caching

Without caching, expensive operations (loading files, parsing data) run on every interaction:

```python
@st.cache_data(ttl=10)  # cache for 10 seconds
def get_reports():
    return load_all_reports()  # reads JSON files

reports = get_reports()  # fast after first call
```

- `@st.cache_data` — for data (DataFrames, lists, dicts). Serializes the return value.
- `@st.cache_resource` — for non-serializable objects (DB connections, ML models).
- `ttl` — time-to-live in seconds. After expiry, next call re-executes the function.

### Cache + st.rerun() interaction (subtle behavior in our app)

When the user saves a new aporte, the code does:
```python
save_contributions(contributions)   # writes to contributions.json on disk
st.rerun()                         # re-runs the script
```

`st.rerun()` triggers a full re-run, but `get_reports()` is still cached (TTL hasn't expired). That's actually fine here because aportes are in a separate file (`contributions.json`) loaded by `load_contributions()` which is NOT cached. Only `get_reports()` (parsed report data) is cached.

If you needed to clear cache programmatically:
```python
st.cache_data.clear()  # clears ALL cached functions
get_reports.clear()    # clears just this function's cache
```

## Multi-page apps

Streamlit auto-discovers Python files in a `pages/` directory:

```
app.py              # main page
pages/
  detalhes.py       # appears as "detalhes" in sidebar navigation
  settings.py       # appears as "settings"
```

Each page is an independent script. The sidebar shows navigation links automatically. Page files run as top-level scripts (no `main()` function needed).

**Important:** Each page must call `st.set_page_config()` as its first Streamlit call. After adding/removing pages, restart the server.

### Naming

The filename becomes the page name in the sidebar. Use prefixes to control order:

```
pages/
  1_visao_geral.py    # "1 visao geral"
  2_detalhes.py       # "2 detalhes"
```

## Flow control

### st.stop()

Halts script execution. Useful for auth gates or validation:

```python
if not reports:
    st.warning("No data")
    st.stop()  # nothing below this line runs
```

### st.rerun()

Forces the script to re-run from the top. Use after state changes that should immediately reflect in the UI:

```python
if st.button("Save"):
    save_data()
    st.rerun()  # UI refreshes with new data
```

**Warning:** Don't call `st.rerun()` unconditionally — it creates an infinite loop.

## Secrets management

For deployment, Streamlit has a built-in secrets system:

```toml
# .streamlit/secrets.toml (local, gitignored)
APP_PASSWORD = "mypassword"
```

```python
password = st.secrets["APP_PASSWORD"]
```

On Streamlit Community Cloud, you set secrets in the dashboard UI. For Railway/Docker, we use environment variables instead (more standard).

## Config file

`.streamlit/config.toml` controls server behavior:

```toml
[server]
headless = true          # no browser auto-open (for deployment)
port = 8501              # default port

[theme]
primaryColor = "#2ecc71"
backgroundColor = "#0e1117"
```

Remove `[theme]` to let users toggle dark/light mode in Settings.

## Tips for this project

1. **Responsive design** — use `use_container_width=True` on charts, 2-column metrics instead of 4, and put chart values in hover tooltips instead of text labels
2. **Plotly over st.bar_chart** — Streamlit has built-in charts but Plotly gives full control over formatting, dual axes, and stacked bars
3. **Cache sparingly** — with a low TTL (10s), cache helps during rapid interactions but doesn't serve stale data after re-parsing
4. **Auth on every page** — in multi-page apps, each page runs independently, so `check_auth()` must be called at the top of each page
