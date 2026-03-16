"""Detalhes do mês: alocação, renda fixa, ações, FIIs, ativos adquiridos."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.models import MonthlyReport
from src.storage import load_all_reports


def format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def responsive_chart(fig, **kwargs):
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
        font=dict(size=11),
    )
    st.plotly_chart(fig, use_container_width=True, **kwargs)


@st.cache_data(ttl=10)
def get_reports() -> list[MonthlyReport]:
    return load_all_reports()


from src.auth import check_auth

st.set_page_config(page_title="Detalhes do Mês", page_icon="🔍", layout="wide")
check_auth()
st.title("🔍 Detalhes do Mês")

reports = get_reports()
if not reports:
    st.warning("Nenhum relatório encontrado.")
    st.stop()

months = {r.date[:7]: r for r in reports}
selected_month = st.sidebar.selectbox(
    "Mês",
    sorted(months.keys(), reverse=True),
    format_func=lambda m: f"{m[5:]}/{m[:4]}",
)
report = months[selected_month]

st.header(f"{selected_month[5:]}/{selected_month[:4]}")

# --- Allocation ---
st.subheader("Alocação Atual")
if report.portfolio:
    df_alloc = pd.DataFrame([
        {"Classe": p.asset_class, "Valor": p.value, "Percentual": p.percentage}
        for p in report.portfolio
    ])
    fig = px.pie(df_alloc, names="Classe", values="Valor", hole=0.4)
    fig.update_traces(textinfo="label+percent", textposition="outside")
    responsive_chart(fig)

st.subheader("Alocação vs Meta")
if report.portfolio:
    current = {p.asset_class: p.percentage for p in report.portfolio}
    target = {t.asset_class: t.percentage for t in report.target_allocation}
    if target:
        classes = list(current.keys())
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Atual", x=classes,
            y=[current.get(c, 0) for c in classes],
            text=[f"{current.get(c, 0):.1f}%" for c in classes],
            textposition="auto",
        ))
        fig.add_trace(go.Bar(
            name="Meta", x=classes,
            y=[target.get(c, 0) for c in classes],
            text=[f"{target.get(c, 0):.1f}%" for c in classes],
            textposition="auto",
        ))
        fig.update_layout(barmode="group", yaxis_title="%")
        responsive_chart(fig)
    else:
        st.info("Meta de alocação não disponível neste relatório.")

# --- Renda Fixa ---
st.subheader("Renda Fixa — Por Indexador")
if report.fixed_income:
    df_fi = pd.DataFrame([
        {
            "Indexador": fi.indexer,
            "Taxa Média": fi.avg_rate,
            "Valor (R$)": fi.value,
            "Percentual (%)": fi.percentage,
        }
        for fi in report.fixed_income
    ])
    fig = px.pie(df_fi, names="Indexador", values="Valor (R$)", hole=0.4)
    fig.update_traces(textinfo="label+percent", textposition="outside")
    responsive_chart(fig)

    df_fi_display = df_fi.copy()
    df_fi_display["Valor (R$)"] = df_fi_display["Valor (R$)"].apply(format_brl)
    df_fi_display["Percentual (%)"] = df_fi_display["Percentual (%)"].apply(lambda x: f"{x:.2f}%")
    st.dataframe(df_fi_display, hide_index=True, use_container_width=True)

# --- Stocks ---
st.subheader("Ações")
if report.stocks:
    df_stocks = pd.DataFrame([
        {
            "Ticker": s.ticker,
            "Qtd": s.quantity,
            "Valor (R$)": s.value,
            "% Carteira": s.percentage,
        }
        for s in sorted(report.stocks, key=lambda x: x.value, reverse=True)
    ])
    display_df = df_stocks.copy()
    display_df["Valor (R$)"] = display_df["Valor (R$)"].apply(format_brl)
    display_df["% Carteira"] = display_df["% Carteira"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    if report.sector_distribution:
        st.markdown("**Distribuição Setorial**")
        df_sector = pd.DataFrame([
            {"Setor": s.sector, "Valor": s.value, "Percentual": s.percentage}
            for s in report.sector_distribution
        ])
        fig = px.pie(df_sector, names="Setor", values="Valor", hole=0.4)
        fig.update_traces(textinfo="label+percent", textposition="outside")
        responsive_chart(fig)

# --- FIIs ---
st.subheader("Fundos Imobiliários")
if report.fiis:
    df_fiis = pd.DataFrame([
        {
            "Ticker": f.ticker,
            "Qtd": f.quantity,
            "Valor (R$)": f.value,
            "% Carteira": f.percentage,
        }
        for f in sorted(report.fiis, key=lambda x: x.value, reverse=True)
    ])
    display_df = df_fiis.copy()
    display_df["Valor (R$)"] = display_df["Valor (R$)"].apply(format_brl)
    display_df["% Carteira"] = display_df["% Carteira"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    if report.fii_segments:
        st.markdown("**Distribuição por Segmento**")
        df_seg = pd.DataFrame([
            {"Segmento": s.segment, "Valor": s.value, "Percentual": s.percentage}
            for s in report.fii_segments
        ])
        fig = px.pie(df_seg, names="Segmento", values="Valor", hole=0.4)
        fig.update_traces(textinfo="label+percent", textposition="outside")
        responsive_chart(fig)

# --- Movimentações ---
st.subheader("Ativos Adquiridos no Mês")
if report.acquired_assets:
    df_mov = pd.DataFrame([
        {"Classe": m.asset_class, "Valor (R$)": m.value}
        for m in report.acquired_assets
    ])
    display_df = df_mov.copy()
    display_df["Valor (R$)"] = display_df["Valor (R$)"].apply(format_brl)
    st.dataframe(display_df, hide_index=True, use_container_width=True)
