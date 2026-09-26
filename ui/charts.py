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


def site_temperature(site: dict, limit_c: float, crop_name: str, lang: str) -> go.Figure:
    """NASA typical year: average daily high and low by month, with the crop's heat limit."""
    months = MONTHS[lang]
    hi = [site["monthly_temp_max_mean_c"][str(m)] for m in range(1, 13)]
    lo = [site["monthly_temp_min_mean_c"][str(m)] for m in range(1, 13)]
    fig = go.Figure()
    fig.add_scatter(x=months, y=lo, name=t("sc_low", lang), mode="lines", line=dict(color=theme.SKY, width=2),
                    hovertemplate="%{x}: %{y:.1f} °C<extra></extra>")
    fig.add_scatter(x=months, y=hi, name=t("sc_high", lang), mode="lines", fill="tonexty", fillcolor="rgba(224,120,42,0.15)",
                    line=dict(color=theme.HEAT_2, width=2.5), hovertemplate="%{x}: %{y:.1f} °C<extra></extra>")
    fig.add_scatter(x=months, y=[limit_c] * 12, name=t("limit_label", lang).format(crop=crop_name, limit=f"{limit_c:.0f}"),
                    mode="lines", line=dict(color=theme.HEAT_3, dash="dash", width=2), hoverinfo="skip")
    fig.update_layout(**theme.plotly_layout(lang, 300))
    fig.update_yaxes(ticksuffix=" °C")
    return fig


def site_humidity(site: dict, lang: str) -> go.Figure:
    """NASA typical year: mean humidity (bars) and the highest wet-bulb temperature (line) by month."""
    months = MONTHS[lang]
    fig = go.Figure()
    fig.add_bar(x=months, y=[site["monthly_rh_mean_pct"][str(m)] for m in range(1, 13)], name=t("sc_rh", lang),
                marker_color=theme.SKY_50, marker_line_color=theme.SKY, marker_line_width=1,
                hovertemplate="%{x}: %{y:.0f}%<extra></extra>")
    fig.add_scatter(x=months, y=[site["monthly_wet_bulb_max_c"][str(m)] for m in range(1, 13)], name=t("sc_wb", lang),
                    mode="lines+markers", yaxis="y2", line=dict(color=theme.GREEN, width=2.5),
                    hovertemplate="%{x}: %{y:.1f} °C<extra></extra>")
    fig.update_layout(**theme.plotly_layout(lang, 300))
    fig.update_layout(yaxis=dict(ticksuffix="%", range=[0, 100]),
                      yaxis2=dict(overlaying="y", side="right", ticksuffix=" °C", tickformat=".0f", showgrid=False))
    return fig


def kit_trace(log: pd.DataFrame, lang: str) -> go.Figure:
    """Croptions Kit readings in arrival order: leaf and air temperature, and the screen position."""
    x = log["seq"].astype(str)
    fig = go.Figure()
    fig.add_scatter(x=x, y=log["air_c"], name=t("kit_air", lang), mode="lines+markers", line=dict(color=theme.SKY, width=2))
    fig.add_scatter(x=x, y=log["leaf_c"], name=t("kit_leaf", lang), mode="lines+markers", line=dict(color=theme.HEAT_2, width=2.5))
    fig.add_bar(x=x, y=log["screen_pct"], name=t("operate_screen", lang), yaxis="y2", marker_color="rgba(30,91,63,0.18)")
    fig.update_layout(**theme.plotly_layout(lang, 300))
    fig.update_layout(yaxis=dict(ticksuffix=" °C"), yaxis2=dict(overlaying="y", side="right", ticksuffix="%", range=[0, 100], tickmode="linear", dtick=20, showgrid=False),
                      xaxis=dict(title=t("kit_reading_no", lang), type="category"))
    return fig


def thermal(image, lang: str) -> go.Figure:
    """Simulated 32 × 24 thermal image (°C)."""
    fig = go.Figure(go.Heatmap(z=image, colorscale="Inferno", zsmooth="best", colorbar=dict(ticksuffix=" °C", thickness=12),
                               hovertemplate="%{z:.1f} °C<extra></extra>"))
    fig.update_layout(**theme.plotly_layout(lang, 300))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, autorange="reversed", scaleanchor="x")
    return fig


def forecast_week(days: list[dict], limit_c: float, lang: str) -> go.Figure:
    """Open-Meteo 7-day forecast: daily maximum temperature (bars, hot days in red) and mean humidity (line)."""
    x = [f'{int(d["date"][8:10])}/{int(d["date"][5:7])}' for d in days]  # day/month
    temps = [d["temp_max_c"] for d in days]
    fig = go.Figure()
    fig.add_bar(x=x, y=temps, name=t("fc_tmax", lang), marker_color=[theme.HEAT_3 if v is not None and v > limit_c else theme.HEAT_1 for v in temps],
                hovertemplate="%{x}: %{y:.1f} °C<extra></extra>")
    fig.add_scatter(x=x, y=[d["rh_mean_pct"] for d in days], name=t("fc_rh", lang), yaxis="y2", mode="lines+markers",
                    line=dict(color=theme.SKY, width=2.5), hovertemplate="%{x}: %{y:.0f}%<extra></extra>")
    fig.add_scatter(x=x, y=[limit_c] * len(x), name=t("fc_limit", lang).format(limit=f"{limit_c:.0f}"), mode="lines",
                    line=dict(color=theme.HEAT_3, dash="dash", width=1.5), hoverinfo="skip")
    fig.update_layout(**theme.plotly_layout(lang, 280))
    fig.update_layout(yaxis=dict(ticksuffix=" °C"), yaxis2=dict(overlaying="y", side="right", ticksuffix="%", range=[0, 100], showgrid=False),
                      xaxis=dict(type="category"))  # "09-26" labels, not dates to parse
    return fig


def solar_months(monthly: dict, lang: str) -> go.Figure:
    """PVGIS monthly solar yield per installed kW (terrain shading included)."""
    fig = go.Figure(go.Bar(x=MONTHS[lang], y=[monthly.get(str(m), monthly.get(m)) for m in range(1, 13)], marker_color=theme.HEAT_1,
                           hovertemplate="%{x}: %{y:.0f} kWh<extra></extra>"))
    fig.update_layout(**theme.plotly_layout(lang, 260))
    fig.update_yaxes(ticksuffix=" kWh")
    return fig


def day_compare(frame: pd.DataFrame, limit_c: float, lang: str) -> go.Figure:
    """One simulated day (operate.simulate_day): outside, fixed shade and smart screen temperatures, and the screen position."""
    fig = go.Figure()
    fig.add_bar(x=frame["time"], y=frame["screen_pct"], name=t("operate_screen", lang), yaxis="y2", marker_color="rgba(30,91,63,0.15)")
    for key, label, colour, dash in (("outside_c", "kd_outside", theme.HEAT_2, "dot"), ("fixed_inside_c", "kd_fixed", theme.SKY, "solid"),
                                     ("smart_inside_c", "kd_smart", theme.GREEN, "solid")):
        fig.add_scatter(x=frame["time"], y=frame[key].round(1), name=t(label, lang), mode="lines", line=dict(color=colour, width=2.5, dash=dash))
    fig.add_scatter(x=frame["time"], y=[limit_c] * len(frame), name=t("fc_limit", lang).format(limit=f"{limit_c:.0f}"), mode="lines",
                    line=dict(color=theme.HEAT_3, dash="dash", width=2), hoverinfo="skip")
    fig.update_layout(**theme.plotly_layout(lang, 340))
    fig.update_layout(yaxis=dict(ticksuffix=" °C"), yaxis2=dict(overlaying="y", side="right", ticksuffix="%", range=[0, 100], tickmode="linear",
                                                            dtick=20, showgrid=False))
    fig.update_xaxes(tickmode="array", tickvals=["00:00", "06:00", "12:00", "18:00", "23:50"])
    return fig
