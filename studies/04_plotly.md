# Plotly — Interactive Charts

> Docs: https://plotly.com/python/
> Express API: https://plotly.com/python/plotly-express/
> Graph Objects API: https://plotly.com/python/graph-objects/

## What it does

Plotly renders interactive charts (zoom, pan, hover tooltips) in the browser. It has two APIs: **Plotly Express** (high-level, quick) and **Graph Objects** (low-level, full control). We use both in this project.

## Plotly Express vs Graph Objects

### Plotly Express — quick charts from DataFrames

```python
import plotly.express as px

# Bar chart
fig = px.bar(df, x="Mês", y="Rentabilidade (%)")

# Pie/donut chart
fig = px.pie(df, names="Classe", values="Valor", hole=0.4)

# Stacked bar
fig = px.bar(df, x="Mês", y=["Ações", "FIIs", "Cupons RF"], barmode="stack")

# Line chart
fig = px.line(df, x="Mês", y="Patrimônio", markers=True)
```

Express is great when your data is in a DataFrame and the chart type is straightforward.

### Graph Objects — full control

```python
import plotly.graph_objects as go

fig = go.Figure()

# Add multiple traces to the same chart
fig.add_scatter(
    x=df["Mês"], y=df["Patrimônio"],
    mode="lines+markers",       # "lines", "markers", "lines+markers", "lines+markers+text"
    name="Patrimônio",          # legend label
    line=dict(color="#2ecc71", width=3),
    hovertemplate="%{x}<br>%{text}<extra></extra>",
    text=[format_brl(v) for v in df["Patrimônio"]],
)

fig.add_bar(
    x=df["Mês"], y=df["Aporte"],
    name="Aporte",
    marker_color="#FF6B6B",
    text=[format_brl(v) for v in df["Aporte"]],
    textposition="outside",
)
```

Use Graph Objects when you need multiple trace types on one chart, dual Y-axes, or fine-grained control.

## Chart types used in this project

### Donut chart (allocation)

```python
fig = px.pie(df, names="Classe", values="Valor", hole=0.4)
fig.update_traces(textinfo="label+percent", textposition="outside")
```

`hole=0.4` makes it a donut. `textposition="outside"` prevents label overlap.

### Stacked bar (proventos breakdown)

```python
fig = px.bar(df, x="Mês", y=["Ações", "FIIs", "Cupons RF"], barmode="stack")
```

Each column in the y-list becomes a stacked segment. Plotly auto-assigns colors and creates a legend.

### Dual Y-axis (aportes: bars + cumulative line)

```python
fig = go.Figure()

fig.add_bar(x=df["Mês"], y=df["Aporte no Mês"], name="Mensal")

fig.add_scatter(
    x=df["Mês"], y=df["Acumulado"],
    name="Acumulado",
    yaxis="y2",                    # binds to second Y axis
)

fig.update_layout(
    yaxis=dict(title="Mensal", tickprefix="R$ "),
    yaxis2=dict(title="Acumulado", tickprefix="R$ ", overlaying="y", side="right"),
)
```

`yaxis="y2"` on the trace + `yaxis2` config in layout creates the right-side axis.

### Grouped bar (allocation vs target)

```python
fig = go.Figure()
fig.add_trace(go.Bar(name="Atual", x=classes, y=current_values))
fig.add_trace(go.Bar(name="Meta", x=classes, y=target_values))
fig.update_layout(barmode="group")
```

## Common customizations

### Layout

```python
fig.update_layout(
    title="Chart Title",
    yaxis_title="R$",
    yaxis_tickprefix="R$ ",              # prefix on tick labels
    yaxis_tickformat=",.",               # thousand separator format
    margin=dict(l=10, r=10, t=40, b=10), # reduce whitespace
    legend=dict(
        orientation="h",                  # horizontal legend
        y=-0.2,                          # below the chart
        x=0.5, xanchor="center",        # centered
    ),
    font=dict(size=11),                  # global font size
    barmode="stack",                     # or "group", "overlay"
)
```

### Hover templates

Control what shows on mouse hover:

```python
fig.add_scatter(
    ...,
    hovertemplate="%{x}<br>%{text}<extra></extra>",
    text=[format_brl(v) for v in values],
)
```

- `%{x}` — x value
- `%{y}` — y value
- `%{text}` — custom text array
- `<extra></extra>` — hides the trace name from the tooltip
- `<br>` — line break in tooltip

### Text labels on bars

```python
fig.add_bar(
    ...,
    text=["R$ 5.000", "R$ 13.000"],
    textposition="outside",    # "inside", "outside", "auto", "none"
)
```

**Mobile consideration:** Text labels on charts overlap on small screens. We switched to hover-only tooltips for the main dashboard by removing `mode="...+text"` and using `hovertemplate` instead.

### Colors

```python
# Named colors
line=dict(color="white", width=2)

# Hex colors
marker_color="#FF6B6B"

# Line styles
line=dict(color="#2ecc71", width=3, dash="dot")  # "solid", "dot", "dash", "dashdot"
```

## Plotly + Streamlit integration

```python
st.plotly_chart(fig, use_container_width=True)
```

`use_container_width=True` makes the chart fill the container width — essential for responsive design. Without it, Plotly uses a fixed default width.

### Our responsive wrapper

```python
def responsive_chart(fig, **kwargs):
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
        font=dict(size=11),
    )
    st.plotly_chart(fig, use_container_width=True, **kwargs)
```

Applied to every chart for consistent mobile-friendly rendering.

## Performance notes

- Plotly charts are rendered client-side (in the browser via JavaScript). The Python code generates a JSON spec that the browser interprets.
- For large datasets (thousands of points), consider using `fig.update_traces(marker=dict(size=3))` to reduce rendering time.
- Our data is small (7-20 data points per chart) so performance isn't a concern.
