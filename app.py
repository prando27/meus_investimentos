"""Streamlit dashboard for investment portfolio visualization."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.models import MonthlyReport
from src.storage import load_all_reports

CONTRIBUTIONS_FILE = Path(__file__).resolve().parent / "data" / "contributions.json"


def load_contributions() -> dict[str, float]:
    """Load manual contributions keyed by YYYY-MM."""
    if CONTRIBUTIONS_FILE.exists():
        return json.loads(CONTRIBUTIONS_FILE.read_text(encoding="utf-8"))
    return {}


def save_contributions(data: dict[str, float]):
    CONTRIBUTIONS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

from src.auth import check_auth

st.set_page_config(page_title="Meus Investimentos", page_icon="📊", layout="wide")
check_auth()


def format_brl(value: float) -> str:
    """Format a number as BRL currency."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl_short(value: float) -> str:
    """Short BRL format for chart labels on mobile."""
    if abs(value) >= 1_000_000:
        return f"R$ {value/1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"R$ {value/1_000:.1f}k"
    return f"R$ {value:,.0f}"


def responsive_chart(fig, **kwargs):
    """Render a Plotly chart with mobile-friendly defaults."""
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
        font=dict(size=11),
    )
    st.plotly_chart(fig, use_container_width=True, **kwargs)


@st.cache_data(ttl=10)
def get_reports() -> list[MonthlyReport]:
    return load_all_reports()


def main():
    st.title("📊 Meus Investimentos")

    reports = get_reports()
    if not reports:
        st.warning("Nenhum relatório encontrado. Execute `uv run python main.py` para processar os PDFs.")
        return

    # Month selector
    months = {r.date[:7]: r for r in reports}
    selected_month = st.sidebar.selectbox(
        "Mês",
        sorted(months.keys(), reverse=True),
        format_func=lambda m: f"{m[5:]}/{m[:4]}",
    )
    report = months[selected_month]

    # --- Summary metrics ---
    st.header(f"Resumo — {selected_month[5:]}/{selected_month[:4]}")
    c1, c2 = st.columns(2)
    c1.metric("Patrimônio", format_brl(report.patrimony))
    c2.metric("Rentabilidade", f"{report.monthly_return_pct:.2f}%")
    c3, c4 = st.columns(2)
    c3.metric("Ganhos no Mês", format_brl(report.monthly_gains))
    c4.metric("Aplicações", format_brl(report.applications))

    # --- Patrimony evolution ---
    contributions = load_contributions()

    if len(reports) > 1:
        st.subheader("Evolução do Patrimônio")

        # Period selector
        all_report_months = sorted([r.date[:7] for r in reports])
        col_pat_start, col_pat_end = st.columns(2)
        with col_pat_start:
            pat_start = st.selectbox(
                "De", all_report_months, index=0,
                format_func=lambda m: f"{m[5:]}/{m[:4]}",
                key="pat_start",
            )
        with col_pat_end:
            pat_end = st.selectbox(
                "Até", all_report_months, index=len(all_report_months) - 1,
                format_func=lambda m: f"{m[5:]}/{m[:4]}",
                key="pat_end",
            )

        filtered_reports = [r for r in reports if pat_start <= r.date[:7] <= pat_end]

        if len(filtered_reports) < 1:
            st.warning("Nenhum relatório no período selecionado.")
        else:
            # Build patrimony data with contributions for filtered period
            pat_rows = []
            cum_aporte = sum(
                contributions.get(r.date[:7], 0.0)
                for r in reports if r.date[:7] < pat_start
            )
            for r in filtered_reports:
                mk = r.date[:7]
                aporte_mes = contributions.get(mk, 0.0)
                cum_aporte += aporte_mes
                pat_rows.append({
                    "Mês": mk,
                    "Patrimônio": r.patrimony,
                    "Aporte no Mês": aporte_mes,
                    "Aportes no Período": cum_aporte - sum(
                        contributions.get(rr.date[:7], 0.0)
                        for rr in reports if rr.date[:7] < pat_start
                    ),
                    "Aportes Acumulados (BTG)": cum_aporte,
                })
            df_pat = pd.DataFrame(pat_rows)

            # Metrics
            aportes_periodo = df_pat["Aportes no Período"].iloc[-1]
            first_pat = df_pat["Patrimônio"].iloc[0]
            last_pat = df_pat["Patrimônio"].iloc[-1]
            col_a, col_b = st.columns(2)
            col_a.metric("Aportes no Período (BTG)", format_brl(aportes_periodo))
            col_b.metric("Crescimento no Período", format_brl(last_pat - first_pat))
            if aportes_periodo > 0:
                organic = last_pat - first_pat - aportes_periodo
                st.metric("Crescimento Orgânico", format_brl(organic))

            # Patrimônio evolution chart
            fig = go.Figure()
            fig.add_scatter(
                x=df_pat["Mês"], y=df_pat["Patrimônio"],
                mode="lines+markers",
                name="Patrimônio",
                hovertemplate="%{x}<br>%{text}<extra></extra>",
                text=[format_brl(v) for v in df_pat["Patrimônio"]],
                line=dict(color="#2ecc71", width=3),
            )
            if aportes_periodo > 0:
                fig.add_scatter(
                    x=df_pat["Mês"], y=df_pat["Aportes Acumulados (BTG)"],
                    mode="lines+markers",
                    name="Aportes Acum. (BTG)",
                    hovertemplate="%{x}<br>%{text}<extra></extra>",
                    text=[format_brl(v) for v in df_pat["Aportes Acumulados (BTG)"]],
                    line=dict(color="#FF6B6B", width=2, dash="dot"),
                )
            fig.update_layout(yaxis_tickprefix="R$ ", yaxis_tickformat=",.", yaxis_title="R$")
            responsive_chart(fig)

        # Aportes mês a mês — include all months from 2025-07
        total_aportes = sum(contributions.values())
        if total_aportes > 0:
            latest_month = max(r.date[:7] for r in reports)
            aporte_rows = []
            cum = 0.0
            y, m = 2025, 7
            while f"{y}-{m:02d}" <= latest_month:
                mk = f"{y}-{m:02d}"
                val = contributions.get(mk, 0.0)
                cum += val
                aporte_rows.append({"Mês": mk, "Aporte no Mês": val, "Acumulado": cum})
                m += 1
                if m > 12:
                    m = 1
                    y += 1
            df_aporte = pd.DataFrame(aporte_rows)

            fig_aporte = go.Figure()
            fig_aporte.add_bar(
                x=df_aporte["Mês"], y=df_aporte["Aporte no Mês"],
                name="Aporte no Mês",
                hovertemplate="%{x}<br>%{text}<extra></extra>",
                text=[format_brl(v) if v > 0 else "" for v in df_aporte["Aporte no Mês"]],
                textposition="outside",
                marker_color="#FF6B6B",
            )
            fig_aporte.add_scatter(
                x=df_aporte["Mês"], y=df_aporte["Acumulado"],
                mode="lines+markers",
                name="Acumulado",
                hovertemplate="%{x}<br>%{text}<extra></extra>",
                text=[format_brl(v) for v in df_aporte["Acumulado"]],
                line=dict(color="#2ecc71", width=2),
                yaxis="y2",
            )
            fig_aporte.update_layout(
                title="Aportes Mensais (BTG Pactual)",
                yaxis=dict(tickprefix="R$ ", title="Mês"),
                yaxis2=dict(tickprefix="R$ ", title="Acumulado", overlaying="y", side="right"),
            )
            responsive_chart(fig_aporte)

    # --- Registrar Aporte (BTG) ---
    with st.sidebar.expander("Registrar Aporte (BTG)"):
        latest = max(r.date[:7] for r in reports)
        all_months = []
        y, m = 2025, 7
        while f"{y}-{m:02d}" <= latest:
            all_months.append(f"{y}-{m:02d}")
            m += 1
            if m > 12:
                m = 1
                y += 1
        all_months.reverse()
        contrib_month = st.selectbox(
            "Mês", all_months,
            format_func=lambda m: f"{m[5:]}/{m[:4]}",
            key="contrib_month",
        )
        current_val = contributions.get(contrib_month, 0.0)
        contrib_value = st.number_input(
            "Valor (R$)", value=current_val, min_value=0.0,
            step=100.0, format="%.2f", key="contrib_value",
        )
        if st.button("Salvar"):
            contributions[contrib_month] = contrib_value
            save_contributions(contributions)
            st.rerun()

    # --- Monthly returns ---
    if len(reports) > 1:
        st.subheader("Rentabilidade Mensal")
        df_ret = pd.DataFrame([
            {"Mês": r.date[:7], "Rentabilidade (%)": r.monthly_return_pct}
            for r in reports
        ])
        fig = px.bar(df_ret, x="Mês", y="Rentabilidade (%)")
        responsive_chart(fig)

    # --- Rentabilidade acumulada ---
    st.subheader("Rentabilidade Acumulada")

    latest_report = max(r.date[:7] for r in reports)
    all_period_months = []
    y, m = 2025, 7
    while f"{y}-{m:02d}" <= latest_report:
        all_period_months.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1

    col_start, col_end = st.columns(2)
    with col_start:
        start_month = st.selectbox(
            "Início", all_period_months,
            index=0,
            format_func=lambda x: f"{x[5:]}/{x[:4]}",
            key="rent_start",
        )
    with col_end:
        end_month = st.selectbox(
            "Fim", all_period_months,
            index=len(all_period_months) - 1,
            format_func=lambda x: f"{x[5:]}/{x[:4]}",
            key="rent_end",
        )

    if start_month <= end_month:
        filtered = [r for r in reports if start_month <= r.date[:7] <= end_month]
        if filtered:
            cum_rows = []
            cum_return = 1.0
            for r in filtered:
                cum_return *= (1 + r.monthly_return_pct / 100)
                cum_rows.append({
                    "Mês": r.date[:7],
                    "Mensal (%)": r.monthly_return_pct,
                    "Acumulada (%)": round((cum_return - 1) * 100, 2),
                })
            df_cum = pd.DataFrame(cum_rows)
            total_cum = df_cum["Acumulada (%)"].iloc[-1]

            st.metric(
                f"Rentabilidade Acumulada ({start_month[5:]}/{start_month[:4]} a {end_month[5:]}/{end_month[:4]})",
                f"{total_cum:.2f}%",
            )

            fig_cum = go.Figure()
            fig_cum.add_bar(
                x=df_cum["Mês"], y=df_cum["Mensal (%)"],
                name="Mensal",
                text=[f"{v:.1f}%" for v in df_cum["Mensal (%)"]],
                textposition="outside",
                marker_color="#3498db",
            )
            fig_cum.add_scatter(
                x=df_cum["Mês"], y=df_cum["Acumulada (%)"],
                mode="lines+markers",
                name="Acumulada",
                hovertemplate="%{x}<br>%{text}<extra></extra>",
                text=[f"{v:.2f}%" for v in df_cum["Acumulada (%)"]],
                line=dict(color="#2ecc71", width=3),
            )
            fig_cum.update_layout(yaxis_title="%")
            responsive_chart(fig_cum)
        else:
            st.info("Nenhum relatório disponível no período selecionado.")
    else:
        st.warning("O mês de início deve ser anterior ou igual ao mês de fim.")

    # --- Proventos ---
    st.subheader("Proventos")

    prov_rows = []
    for r in reports:
        if r.proventos and r.proventos.total > 0:
            prov_rows.append({
                "Mês": r.date[:7],
                "Ações": r.proventos.acoes,
                "FIIs": r.proventos.fiis,
                "Cupons RF": r.proventos.cupons_rf,
                "Total": r.proventos.total,
            })
    if prov_rows:
        df_prov = pd.DataFrame(prov_rows)

        # Current month metrics
        if report.proventos and report.proventos.total > 0:
            prov = report.proventos
            c1, c2 = st.columns(2)
            c1.metric("Ações", format_brl(prov.acoes))
            c2.metric("FIIs", format_brl(prov.fiis))
            c3, c4 = st.columns(2)
            c3.metric("Cupons RF", format_brl(prov.cupons_rf))
            c4.metric("Total", format_brl(prov.total))

        # Accumulated total
        st.metric("Proventos Acumulados", format_brl(df_prov["Total"].sum()))

        # Stacked bar chart
        fig = px.bar(
            df_prov, x="Mês", y=["Ações", "FIIs", "Cupons RF"],
            barmode="stack",
            title="Evolução Mensal de Proventos",
        )
        fig.update_layout(
            yaxis_tickprefix="R$ ", yaxis_title="Proventos",
            legend_title="Fonte",
        )
        fig.add_scatter(
            x=df_prov["Mês"], y=df_prov["Total"],
            mode="lines+markers",
            name="Total",
            hovertemplate="%{x}<br>%{text}<extra></extra>",
            text=[format_brl(v) for v in df_prov["Total"]],
            line=dict(color="white", width=2),
        )
        responsive_chart(fig)

        # Evolution table
        display_prov = df_prov.copy()
        display_prov["Mês"] = display_prov["Mês"].apply(lambda m: f"{m[5:]}/{m[:4]}")
        for col in ["Ações", "FIIs", "Cupons RF", "Total"]:
            display_prov[col] = display_prov[col].apply(format_brl)
        st.dataframe(display_prov, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
