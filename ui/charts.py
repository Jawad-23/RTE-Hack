"""Plotly charts in the Croptions style. Owned by Me."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from i18n import t
from planner.schemas import SETUPS
from ui import theme
from ui.components import MONTHS
from ui.state import setup_label


def _line(setup: str) -> dict:
    s = theme.SETUP_STYLE[setup]
    return dict(color=s["color"], dash=s["dash"], width=s["width"])


def inside_temperature(monthly: pd.DataFrame, limit_c: float, crop_name: str, lang: str) -> go.Figure:
    """Average daily maximum by month for each setup, with the crop heat limit and the too-hot zone shaded."""
    months = MONTHS[lang]
    fig = go.Figure()
    top = max(float(monthly[SETUPS].max().max()), limit_c) + 3
    fig.add_hrect(y0=limit_c, y1=top, fillcolor=theme.IMPOSSIBLE_FILL, opacity=0.55, line_width=0, layer="below")
    for setup in SETUPS:
        fig.add_scatter(x=months, y=monthly[setup].round(1), name=setup_label(setup, lang), mode="lines", line=_line(setup),
                        hovertemplate="%{x}: %{y:.1f} °C<extra>" + setup_label(setup, lang) + "</extra>")
    fig.add_scatter(x=months, y=[limit_c] * 12, name=t("limit_label", lang).format(crop=crop_name, limit=f"{limit_c:.0f}"),
                    mode="lines", line=dict(color=theme.HEAT_3, dash="dash", width=2), hoverinfo="skip")
    fig.update_layout(**theme.plotly_layout(lang, 380))
    fig.update_yaxes(ticksuffix=" °C", range=[min(float(monthly[SETUPS].min().min()), limit_c) - 3, top])
    return fig


def summer_day(day: dict, lang: str) -> go.Figure:
    """Hottest day: solar output (filled) vs chiller cooling electricity (dashed), kWh per hour."""
    fig = go.Figure()
    fig.add_scatter(x=day["hour"], y=day["solar_kwh"], name=t("solar_prod", lang), mode="lines", fill="tozeroy",
                    line=dict(color="#C9A227", width=2.5, shape="spline"), fillcolor="rgba(233,185,47,0.35)",
                    hovertemplate="%{x}:00 · %{y:.1f} kWh<extra></extra>")
    fig.add_scatter(x=day["hour"], y=day["cooling_kwh"], name=t("cool_need", lang), mode="lines",
                    line=dict(color=theme.SKY, width=2.5, dash="dash", shape="spline"), hovertemplate="%{x}:00 · %{y:.1f} kWh<extra></extra>")
    fig.update_layout(**theme.plotly_layout(lang, 300))
    fig.update_xaxes(tickvals=[0, 6, 12, 18, 23], ticktext=["00:00", "06:00", "12:00", "18:00", "23:00"])
    fig.update_yaxes(ticksuffix=" kWh")
    return fig


def cumulative_profit(options: list[dict], rec: dict | None, lang: str) -> go.Figure:
    """Cumulative profit over 10 years for each setup of one crop; a marker where the recommendation pays back."""
    years = list(range(11))
    fig = go.Figure()
    for o in options:
        if o["capex_qar"] is None:
            continue
        y = [-o["capex_qar"] + o["profit_qar_year"] * yr for yr in years]
        fig.add_scatter(x=years, y=y, name=setup_label(o["setup"], lang), mode="lines", line=_line(o["setup"]),
                        hovertemplate="%{x}: %{y:,.0f} QAR<extra>" + setup_label(o["setup"], lang) + "</extra>")
    if rec and rec.get("payback_years") is not None and rec["payback_years"] <= 10:
        fig.add_scatter(x=[rec["payback_years"]], y=[0], mode="markers", showlegend=False, hoverinfo="skip",
                        marker=dict(size=13, color=theme.SAND_50, line=dict(color=theme.GREEN, width=3)))
    fig.add_hline(y=0, line_color=theme.SAND_400, line_width=1.5)
    fig.update_layout(**theme.plotly_layout(lang, 300))
    fig.update_xaxes(title_text=t("years", lang), dtick=2)
    fig.update_yaxes(tickformat="~s")
    return fig
