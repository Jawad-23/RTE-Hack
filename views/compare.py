"""Compare sites: the same farm at two places, side by side. Owned by Me."""

import streamlit as st

from i18n import t
from planner import optimizer
from ui import insights, state
from ui import components as ui

lang = state.lang()
ss = st.session_state
demos = state.demo_sites()

st.markdown(f'<h1 style="font-size:32px;margin:8px 0 0">{t("c_title", lang)}</h1><p class="cr-sub">{t("c_sub", lang)}</p>',
            unsafe_allow_html=True)

# Site choices: the demo pins plus the current pin.
choices = {f"demo:{r.key}": (r.name_ar if lang == "ar" else r.name_en, float(r.lat), float(r.lon), r.kind) for r in demos.itertuples()}
if ss["pin"] and not state.site_name(*ss["pin"], lang):
    choices["pin"] = (t("p_pinned", lang), ss["pin"][0], ss["pin"][1], None)
keys = list(choices)
if ss.get("cmp_a") not in keys:
    ss["cmp_a"] = "pin" if "pin" in choices else keys[-1]
if ss.get("cmp_b") not in keys or ss["cmp_b"] == ss["cmp_a"]:
    ss["cmp_b"] = next(k for k in keys if k != ss["cmp_a"]) if len(keys) > 1 else keys[0]

with st.container(key="card_pick"):
    c1, c2, c3 = st.columns([1, 1, 0.8], vertical_alignment="bottom")
    a = c1.selectbox(t("c_site_a", lang), keys, index=keys.index(ss["cmp_a"]) if ss["cmp_a"] in keys else 0,
                     format_func=lambda k: f"{choices[k][0]} · {state.coords(choices[k][1], choices[k][2])}")
    b = c2.selectbox(t("c_site_b", lang), keys, index=keys.index(ss["cmp_b"]) if ss["cmp_b"] in keys else 0,
                     format_func=lambda k: f"{choices[k][0]} · {state.coords(choices[k][1], choices[k][2])}")
    run = c3.button(f"{t('c_run', lang)} →", type="primary", use_container_width=True)
    st.markdown(f'<p class="cr-note">{t("c_inputs", lang).format(area=state.n0(ss["area"]), budget=state.n0(ss["budget"]), priority=t("pr_" + ss["priority"], lang))}</p>',
                unsafe_allow_html=True)

if run:
    ss["cmp_a"], ss["cmp_b"] = a, b
    with st.spinner(t("a_title", lang)):
        args = dict(area_m2=float(ss["area"]), budget_qar=float(ss["budget"]), priority=ss["priority"], crop=ss["crop"])
        ss["compare"] = {k: optimizer.plan(choices[key][1], choices[key][2], **args) | {"_key": key} for k, key in (("a", a), ("b", b))}

cmp = ss.get("compare")
if not cmp:
    st.stop()


def verdict(plan: dict) -> str:
    rec = plan.get("recommended")
    if not rec:
        return t("none_title", lang)
    v = t("verdict", lang).format(crop=state.crop_in_sentence(rec["crop"], lang), setup=t(f"setupv_{rec['setup']}", lang))
    pay = t("verdict_pay", lang).format(years=state.n1(rec["payback_years"])) if rec["payback_years"] is not None else t("verdict_nopay", lang)
    return f"{v} {pay}"


def pad_drop(plan: dict) -> float | None:
    try:
        return insights.wet_pad_drop_c(state.climate_for(plan["inputs"]["lat"], plan["inputs"]["lon"]), plan["inputs"]["area_m2"])
    except Exception:
        return None


pa, pb = cmp["a"], cmp["b"]
da, db = pad_drop(pa), pad_drop(pb)
rh_a, rh_b = pa["site"].get("hottest_month_rh_mean_pct"), pb["site"].get("hottest_month_rh_mean_pct")
humid_a = rh_a is not None and rh_b is not None and rh_a > rh_b
kind_label = lambda humid: t("t_coast" if humid else "t_inland", lang)  # noqa: E731

left, mid, right = st.columns([1, 0.62, 1], gap="medium")
for col, plan, drop, humid in ((left, pa, da, humid_a), (right, pb, db, not humid_a)):
    name, lat, lon, _ = choices.get(plan["_key"], (t("p_pinned", lang), plan["inputs"]["lat"], plan["inputs"]["lon"], None))
    col.markdown(ui.site_card(name, kind_label(humid), lat, lon, plan, drop, verdict(plan), lang, humid), unsafe_allow_html=True)

ta, tb = pa["site"].get("temp_max_c"), pb["site"].get("temp_max_c")
same_heat = ta is not None and tb is not None and abs(ta - tb) <= 2
different_air = rh_a is not None and rh_b is not None and abs(rh_a - rh_b) >= 15
headline = t("c_strip1", lang) if same_heat and different_air else t("c_strip1_generic", lang)
detail = ""
if da is not None and db is not None:
    dry, wet = (db, da) if humid_a else (da, db)
    detail = t("c_strip3", lang).format(dry=f"{dry:.0f}", wet=f"{wet:.0f}")
mid.markdown(f'<div class="cr-strip"><div class="dots">● ●</div><h3>{headline}</h3><p style="color:#FFFDF8;font-size:15px">{t("c_strip2", lang)}</p>'
             f'<p>{detail}</p></div>', unsafe_allow_html=True)

c1, c2, _ = st.columns([0.6, 1, 2])
if c1.button(t("c_change", lang), use_container_width=True):
    ss["compare"] = None
    st.rerun()
if c2.button(t("c_ask", lang), type="primary", use_container_width=True):
    state.open_chat(t("c_ask_q", lang).format(a=choices.get(pa["_key"], ("A",))[0], b=choices.get(pb["_key"], ("B",))[0]))
    st.rerun()
