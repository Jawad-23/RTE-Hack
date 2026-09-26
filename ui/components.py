"""HTML building blocks styled by ui/theme.py. Owned by Me.

Every function returns an HTML string for st.html / st.markdown(unsafe_allow_html=True).
Text from data files is escaped; numbers are formatted by ui/state.py.
"""

from __future__ import annotations

from html import escape

from i18n import t
from planner.schemas import MIN_COVERAGE_PCT, STATUS
from ui import theme
from ui.state import coords, crop_label, n0, n1, setup_label

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
}


def brand(lang: str) -> str:
    return f'<div class="cr-brand"><span class="mark"><span></span></span>{escape(t("brand", lang))}</div>'


def title(text: str, sub: str | None = None) -> str:
    return f'<p class="cr-title">{escape(text)}</p>' + (f'<p class="cr-sub">{escape(sub)}</p>' if sub else "")


def tiles(items: list[dict]) -> str:
    """items: [{k, v, unit, note, water?}] -> a responsive row of metric tiles."""
    cells = []
    for it in items:
        cls = "v water" if it.get("water") else "v"
        unit = f"<small>{escape(it['unit'])}</small>" if it.get("unit") else ""
        cells.append(f'<div class="cr-tile"><div class="k">{escape(it["k"])}</div><div class="{cls}">{escape(it["v"])}{unit}</div>'
                     f'<div class="n">{escape(it.get("note", ""))}</div></div>')
    return f'<div class="cr-tiles">{"".join(cells)}</div>'


def legend_status(lang: str) -> str:
    out = []
    for s in STATUS:
        bg, fg, icon = theme.STATUS_STYLE[s]
        out.append(f'<span><i style="background:{bg};color:{fg}">{icon}</i>{escape(t(f"status_{s}", lang))}</span>')
    return f'<div class="cr-legend">{"".join(out)}</div>'


def calendar(cal: dict, chosen: str | None, lang: str) -> str:
    """Plan calendar {crop: {"1": status, ...}} -> month grid with ✓ ! ✕ cells."""
    head = "".join(f"<th>{m}</th>" for m in MONTHS[lang])
    rows = []
    for crop, months in cal.items():
        tag = f' <span class="cr-pill soft">{escape(t("chosen", lang))}</span>' if crop == chosen else ""
        cells = []
        for m in range(1, 13):
            status = months.get(str(m), "impossible")
            bg, fg, icon = theme.STATUS_STYLE[status]
            cells.append(f'<td class="cell" style="background:{bg};color:{fg}" title="{escape(t(f"status_{status}", lang))}">{icon}</td>')
        rows.append(f'<tr><td class="crop">{escape(crop_label(crop, lang))}{tag}</td>{"".join(cells)}</tr>')
    return f'<table class="cr-cal"><thead><tr><th></th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _swatch(setup: str) -> str:
    st_ = theme.SETUP_STYLE[setup]
    style = {"dot": "dotted", "dash": "dashed", "solid": "solid"}[st_["dash"]]
    return f'<span class="cr-swatch" style="border-top:{3 if st_["width"] < 4 else 4}px {style} {st_["color"]}"></span>'


def coverage_color(pct: float) -> str:
    if pct >= MIN_COVERAGE_PCT:
        return theme.GREEN
    return theme.HEAT_1 if pct >= 60 else theme.HEAT_2


def comparison(options: list[dict], rec: dict | None, lang: str) -> str:
    """Setup comparison table for one crop: months, coverage bar, costs, payback, 10-year profit, badges."""
    cols = ["c_setup", "c_months", "c_cov", "c_cost", "c_profit", "c_pay", "c_p10"]
    head = "".join(f"<th>{escape(t(c, lang))}</th>" for c in cols)
    rows = []
    for o in options:
        is_rec = rec is not None and o["setup"] == rec["setup"] and o["crop"] == rec["crop"]
        badges = []
        if is_rec:
            badges.append(f'<span class="cr-pill green">{escape(t("recommended", lang))}</span>')
        if o["coverage_pct"] < MIN_COVERAGE_PCT:
            badges.append(f'<span class="cr-pill warn">! {escape(t("badge_too_hot", lang))}</span>')
        if o["capex_qar"] is not None and o["capex_qar"] > 0 and any("budget" in r for r in o.get("fail_reasons", [])):
            badges.append(f'<span class="cr-pill bad">{escape(t("badge_over_budget", lang))}</span>')
        pct = o["coverage_pct"]
        bar = f'<span class="cr-bar"><b style="width:{max(2, min(100, pct)):.0f}%;background:{coverage_color(pct)}"></b></span>'
        payback = "—" if o["payback_years"] is None else f'{n1(o["payback_years"])} {t("years", lang)}'
        rows.append(
            f'<tr class="{"rec" if is_rec else ""}">'
            f'<td><div class="strong">{_swatch(o["setup"])}{escape(setup_label(o["setup"], lang))}</div>'
            f'<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">{"".join(badges)}</div></td>'
            f'<td>{len(o["growing_months"])} {escape(t("of12", lang))}</td>'
            f'<td class="num">{pct:.0f} %{bar}</td>'
            f'<td class="num">{n0(o["capex_qar"])} {escape(t("qar", lang))}</td>'
            f'<td class="num">{n0(o["profit_qar_year"])} {escape(t("qar", lang))}</td>'
            f'<td class="num">{escape(payback)}</td>'
            f'<td class="num strong">{n0(o["profit_10y_qar"])} {escape(t("qar", lang))}</td></tr>'
        )
    return f'<div style="overflow-x:auto"><table class="cr-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def sources(plan: dict, lang: str) -> str:
    """Data sources list with links and fetch dates."""
    rows = []
    for s in plan.get("sources", []):
        url = s.get("url", "")
        name = escape(s.get("name", ""))
        link = f'<a href="{escape(url)}" target="_blank">{name}</a>' if url.startswith("http") else f"<b>{name}</b> <span class='cr-mono'>{escape(url)}</span>"
        fetched = f'<span class="cr-note">{escape(t("fetched", lang))} {escape(s["fetched"])}</span>' if s.get("fetched") else ""
        rows.append(f'<div class="cr-src"><div>{link}</div>{fetched}</div>')
    return "".join(rows)


def site_card(site_label: str, kind_label: str | None, lat: float, lon: float, plan: dict, pad_drop_c: float | None,
              verdict: str, lang: str, humid: bool) -> str:
    """One site's column on the compare page."""
    s = plan.get("site", {})
    rec = plan.get("recommended")
    pad = next((o for o in plan.get("options", []) if o["setup"] == "wet_pad" and rec and o["crop"] == rec["crop"]), None)
    kind = f'<span class="cr-pill {"sky" if humid else "sand"}">{escape(kind_label)}</span>' if kind_label else ""
    rh = s.get("hottest_month_rh_mean_pct")
    rec_cls = "none" if rec is None else ("green" if rec["setup"] == "chiller" else "sky")
    rows = []
    if rec:
        rows.append(f'<div class="row"><span>{escape(t("c_best", lang))}</span><b>{escape(setup_label(rec["setup"], lang))}</b></div>')
    if pad_drop_c is not None:
        rows.append(f'<div class="row"><span>{escape(t("c_padcool", lang))}</span><b>−{pad_drop_c:.0f} °C</b></div>')
    if rec:
        rows.append(f'<div class="row"><span>{escape(t("k_cost", lang))}</span><b>{n0(rec["capex_qar"])} {escape(t("qar", lang))}</b></div>')
        pb = "—" if rec["payback_years"] is None else f'{n1(rec["payback_years"])} {t("years", lang)}'
        rows.append(f'<div class="row"><span>{escape(t("k_pay", lang))}</span><b>{escape(pb)}</b></div>')
    if pad:
        pct = pad["coverage_pct"]
        rows.append(f'<div style="padding-top:12px"><div class="cr-note">{escape(t("c_padcov", lang))}</div>'
                    f'<div style="display:flex;align-items:center;gap:10px;margin-top:8px"><span class="cr-bar" style="flex:1;width:auto;height:8px;margin:0">'
                    f'<b style="width:{max(2, min(100, pct)):.0f}%;background:{coverage_color(pct)}"></b></span><b class="num">{pct:.0f} %</b></div></div>')
    return f"""
<div class="cr-site-card">
  <div class="head">{kind}<div style="font-size:22px;font-weight:600;margin-top:8px">{escape(site_label)}</div>
    <div class="cr-mono" style="margin-top:6px">{coords(lat, lon)}</div></div>
  <div class="stats">
    <div><div class="cr-note">{escape(t("c_peak", lang))}</div><div class="big"><span style="color:{theme.HEAT_3}">■</span> {n0(s.get("temp_max_c"))} °C</div></div>
    <div style="background:{theme.SKY_50 if humid else 'transparent'}"><div class="cr-note">{escape(t("c_hum", lang))}</div>
      <div class="big" style="color:{theme.SKY_700}">{n0(rh)} %</div><div class="cr-note" style="color:{theme.SKY_700}">{escape(t("c_wet" if humid else "c_dry", lang))}</div></div>
  </div>
  <div class="rec {rec_cls}"><div class="cr-note" style="color:inherit;opacity:.85">{escape(t("recommendation", lang))}</div><div class="v">{escape(verdict)}</div></div>
  <div class="rows">{"".join(rows)}</div>
</div>"""


KIT_ART = """<svg viewBox="0 0 240 200" width="100%" role="img" aria-label="Croptions Kit pod" style="max-width:260px">
  <circle cx="176" cy="44" r="22" fill="#E9B92F"/><circle cx="176" cy="44" r="34" fill="#E9B92F" opacity=".18"/>
  <rect x="96" y="70" width="12" height="100" rx="4" fill="#CFC3AA"/>
  <rect x="62" y="44" width="80" height="44" rx="10" fill="#FFFDF8" stroke="#EBDDBF" stroke-width="2"/>
  <rect x="70" y="36" width="64" height="12" rx="3" fill="#1E5B3F" transform="skewX(-12)"/>
  <circle cx="86" cy="66" r="10" fill="#1E2A22"/><circle cx="86" cy="66" r="5" fill="#E0782A"/>
  <rect x="104" y="58" width="28" height="6" rx="3" fill="#2B78B0"/><rect x="104" y="70" width="20" height="6" rx="3" fill="#6E7F62"/>
  <path d="M86 78 L60 150 M86 78 L112 150" stroke="#E0782A" stroke-width="1.5" stroke-dasharray="3 4" opacity=".8"/>
  <g fill="#A7C4A0"><ellipse cx="44" cy="168" rx="26" ry="12"/><ellipse cx="96" cy="172" rx="22" ry="10"/><ellipse cx="150" cy="168" rx="26" ry="12"/></g>
  <g fill="#E0782A" opacity=".85"><circle cx="58" cy="164" r="4"/><circle cx="150" cy="166" r="3"/></g>
  <rect x="0" y="178" width="240" height="22" rx="6" fill="#CFC3AA" opacity=".5"/>
</svg>"""


def kit_pitch(lang: str, price_qar: float | None = None, service_qar: float | None = None, compact: bool = False,
              pod_area_m2: float | None = None) -> str:
    """Marketing block for the Croptions Kit: what it is, what each part does, and the placeholder price."""
    features = "".join(
        f'<div class="f"><div class="i">{icon}</div><div><b>{escape(t(f"kp_f{i}", lang))}</b><p>{escape(t(f"kp_f{i}t", lang))}</p></div></div>'
        for i, icon in enumerate(("🌡", "💧", "🧭", "☀"), start=1)
    )
    price = ""
    if price_qar is not None:
        price = (f'<div class="price">{escape(t("kp_price", lang).format(price=n0(price_qar), service=n0(service_qar)))}'
                 f'<span>{escape(t("kp_price_note", lang).format(area=n0(pod_area_m2)))}</span></div>')
    art = "" if compact else f'<div class="art">{KIT_ART}</div>'
    return (f'<div class="cr-kit{" compact" if compact else ""}"><div class="copy"><span class="cr-pill sand">{escape(t("kp_eyebrow", lang))}</span>'
            f'<h2>{escape(t("kp_title", lang))}</h2><p class="lead">{escape(t("kp_sub", lang))}</p>'
            f'<div class="feats">{features}</div>{price}</div>{art}</div>')


def investment(options: list[dict], rec: dict | None, lang: str) -> str:
    """Investment table for one crop: CapEx, OpEx, revenue, NPV, IRR, break-even price and the downside payback."""
    cols = ["c_setup", "i_capex", "i_opex", "i_revenue", "i_npv", "i_irr", "i_breakeven", "i_downside"]
    head = "".join(f"<th>{escape(t(c, lang))}</th>" for c in cols)
    rows = []
    for o in options:
        is_rec = rec is not None and o["setup"] == rec["setup"] and o["crop"] == rec["crop"]
        npv = o.get("npv_qar")
        npv_cls = "" if npv is None else ("good" if npv >= 0 else "bad")
        irr = "—" if o.get("irr_pct") is None else f'{n1(o["irr_pct"])} %'
        be, price = o.get("breakeven_price_qar_kg"), o.get("price_qar_kg")
        be_cell = "—" if be is None else f'{n1(be)} <small>/ {n1(price)}</small>'
        down = "—" if o.get("payback_price_down_years") is None else f'{n1(o["payback_price_down_years"])} {t("years", lang)}'
        rows.append(
            f'<tr class="{"rec" if is_rec else ""}"><td><div class="strong">{_swatch(o["setup"])}{escape(setup_label(o["setup"], lang))}</div></td>'
            f'<td class="num">{n0(o["capex_qar"])}</td><td class="num">{n0(o["opex_qar_year"])}</td><td class="num">{n0(o["revenue_qar_year"])}</td>'
            f'<td class="num strong {npv_cls}">{n0(npv)}</td><td class="num">{escape(irr)}</td>'
            f'<td class="num">{be_cell}</td><td class="num">{escape(down)}</td></tr>')
    return f'<div style="overflow-x:auto"><table class="cr-table cr-invest"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
