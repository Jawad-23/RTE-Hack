"""Croptions design tokens, page CSS and the Plotly look. Owned by Me.

Values come from ui-demo/Croptions Design System.dc.html so the app matches the prototype.
"""

from __future__ import annotations

# Colour tokens
SAND_50 = "#FFFDF8"    # surface
SAND_100 = "#F5F0E6"   # page
SAND_200 = "#EFE8DA"   # fill
SAND_300 = "#E6DDCB"   # line
SAND_400 = "#CFC3AA"   # border
INK = "#1E2A22"
INK_MUTED = "#5E6558"
GREEN_50 = "#EEF4EE"
GREEN_100 = "#E3EDE5"
GREEN = "#1E5B3F"      # primary
GREEN_700 = "#174A33"  # hover
ACCENT = "#EBDDBF"     # accent sand
SKY_50 = "#E2EEF7"
SKY = "#2B78B0"
SKY_700 = "#1F5F8C"
HEAT_1 = "#E9B92F"
HEAT_2 = "#E0782A"
HEAT_3 = "#B3261E"
RISKY_FILL = "#FBEBC8"
IMPOSSIBLE_FILL = "#F6D9D4"

STATUS_STYLE = {  # crop calendar cells: background, text, icon
    "good": ("#DDEBDF", GREEN, "✓"),
    "risky": (RISKY_FILL, "#7A5200", "!"),
    "impossible": (IMPOSSIBLE_FILL, "#9E2A1F", "✕"),
}

# One line style per setup, shared by every chart and table legend.
SETUP_STYLE = {
    "open_field": {"color": "#A88450", "dash": "dot", "width": 2.5},
    "shade_net": {"color": "#6E7F62", "dash": "dash", "width": 2.5},
    "wet_pad": {"color": SKY, "dash": "solid", "width": 2.5},
    "chiller": {"color": GREEN, "dash": "solid", "width": 4},
    "nir_screen_wet_pad": {"color": "#76528B", "dash": "dash", "width": 2.5},
    "agrivoltaic_fixed": {"color": "#9A5528", "dash": "dot", "width": 2.5},
    "agrivoltaic_louver": {"color": "#176D74", "dash": "solid", "width": 2.5},
}

FONT_STACK = "'IBM Plex Sans', 'IBM Plex Sans Arabic', system-ui, sans-serif"
FONT_STACK_AR = "'IBM Plex Sans Arabic', 'IBM Plex Sans', system-ui, sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, monospace"


def plotly_layout(lang: str = "en", height: int = 360) -> dict:
    """Shared Plotly layout: transparent background, design fonts, quiet grid."""
    return dict(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_STACK_AR if lang == "ar" else FONT_STACK, size=14, color=INK),
        xaxis=dict(showgrid=False, zeroline=False, linecolor=SAND_300, tickfont=dict(color=INK_MUTED)),
        yaxis=dict(gridcolor=SAND_300, zeroline=False, tickfont=dict(color=INK_MUTED)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=13)),
        hoverlabel=dict(bgcolor=SAND_50, bordercolor=SAND_400, font=dict(family=FONT_STACK, color=INK)),
    )


PLOTLY_CONFIG = {"displayModeBar": False}


def css(lang: str) -> str:
    """All page CSS. Arabic switches the page to right-to-left and the Arabic font first."""
    font = FONT_STACK_AR if lang == "ar" else FONT_STACK
    direction = "rtl" if lang == "ar" else "ltr"
    align = "right" if lang == "ar" else "left"
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, .stApp, .stApp *:not([data-testid="stIconMaterial"]):not(code):not(pre):not(.cr-mono) {{ font-family: {font}; }}
.stApp {{ background: {SAND_100}; color: {INK}; }}
header[data-testid="stHeader"] {{ display: none; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none; }}
.block-container, [data-testid="stMainBlockContainer"] {{ max-width: 1320px; padding: 0 40px 96px; }}
.stMain [data-testid="stVerticalBlock"] {{ gap: 16px; }}
.stMain, .stMain p, .stMain li, .stMain label, .stMain h1, .stMain h2, .stMain h3 {{ direction: {direction}; text-align: {align}; }}
.stMain h1, .stMain h2, .stMain h3 {{ font-family: {font}; letter-spacing: -0.015em; color: {INK}; }}
.stMain [data-testid="stMetricValue"], .stMain [data-testid="stMetricValue"] * {{ direction: ltr; unicode-bidi: isolate; text-align: {align}; }}
.stMain a {{ color: {GREEN}; }}

/* Top bar */
.st-key-topbar {{
  background: {SAND_50}; border-bottom: 1px solid {SAND_300};
  margin: 0 -40px 24px !important; padding: 10px 40px; width: calc(100% + 80px) !important; max-width: none !important; position: sticky; top: 0; z-index: 50;
}}
.st-key-topbar [data-testid="stHorizontalBlock"] {{ align-items: center; gap: 8px; }}
.cr-brand {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 20px; color: {INK}; white-space: nowrap; }}
.cr-brand .mark {{ width: 32px; height: 32px; border-radius: 10px; background: {GREEN}; display: grid; place-items: center; }}
.cr-brand .mark span {{ width: 12px; height: 12px; border-radius: 50%; background: {ACCENT}; }}
[data-testid="stPageLink"] a {{ border-radius: 10px; padding: 6px 10px; white-space: nowrap; }}
[data-testid="stPageLink"] a p {{ white-space: nowrap; overflow: visible; }}
[data-testid="stPageLink"] a p {{ font-size: 15px; color: {INK}; font-weight: 500; }}
[data-testid="stPageLink"] a:hover {{ background: {GREEN_50}; }}
[data-testid="stPageLink"] a[aria-current="page"], [data-testid="stPageLink-NavLink"][aria-current="page"] {{ background: {GREEN_100}; }}
[data-testid="stPageLink"] a[aria-current="page"] p {{ color: {GREEN}; }}

/* Buttons */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {{
  border-radius: 10px; font-weight: 600; min-height: 44px; padding: 8px 18px;
  border: 1px solid {SAND_400}; background: {SAND_50}; color: {INK};
}}
.stButton button p, .stDownloadButton button p, [data-testid="stPopover"] button p {{ font-weight: 600; font-size: 15px; }}
.stButton button:hover, .stDownloadButton button:hover {{ background: #F7F1E4; border-color: {SAND_400}; color: {INK}; }}
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] {{ background: {GREEN}; border: 0; color: {SAND_50}; }}
.stButton button[kind="primary"]:hover {{ background: {GREEN_700}; color: {SAND_50}; }}
.stButton button:disabled {{ background: #9AAE9F; color: {SAND_50}; border: 0; }}
.stButton button:focus-visible {{ outline: 3px solid {SKY}; outline-offset: 2px; }}

/* Inputs */
[data-baseweb="input"], [data-baseweb="select"] > div, .stNumberInput > div > div {{
  border-radius: 10px; background: {SAND_50}; border-color: {SAND_400};
}}
[data-testid="stWidgetLabel"] p {{ font-size: 14px; font-weight: 500; color: {INK}; }}

/* Cards made from keyed containers */
[class*="st-key-card"] {{
  background: {SAND_50}; border-radius: 20px; padding: 24px;
  box-shadow: 0 1px 2px rgba(60,45,20,.08);
}}
.cr-card {{ background: {SAND_50}; border-radius: 20px; padding: 24px; box-shadow: 0 1px 2px rgba(60,45,20,.08); }}
.cr-title {{ font-size: 18px; font-weight: 600; margin: 0; color: {INK}; }}
.cr-sub {{ font-size: 14px; color: {INK_MUTED}; margin: 2px 0 0; }}
.cr-eyebrow {{ font-size: 14px; color: {INK_MUTED}; }}
.cr-mono {{ font-family: {MONO}; font-size: 13px; color: {INK_MUTED}; direction: ltr; unicode-bidi: isolate; }}
.cr-note {{ font-size: 14px; color: {INK_MUTED}; }}
.cr-pill {{ display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 3px 10px; font-size: 13px; font-weight: 600; }}
.cr-pill.green {{ background: {GREEN}; color: {SAND_50}; }}
.cr-pill.sand {{ background: {ACCENT}; color: {GREEN}; }}
.cr-pill.soft {{ background: {GREEN_50}; color: {GREEN}; }}
.cr-pill.sky {{ background: {SKY_50}; color: {SKY_700}; }}
.cr-pill.warn {{ background: {RISKY_FILL}; color: #8A4B0B; }}
.cr-pill.bad {{ background: {IMPOSSIBLE_FILL}; color: #9E2A1F; }}
.cr-banner {{ background: {RISKY_FILL}; color: #5A3D00; border-radius: 14px; padding: 12px 16px; font-size: 14px; }}

/* Recommendation hero */
.st-key-hero {{ background: {GREEN}; border-radius: 20px; padding: 36px 36px 28px; color: {SAND_50}; }}
.st-key-hero.bad, .st-key-hero_none {{ background: #3A2A22; border-radius: 20px; padding: 36px; color: {SAND_50}; }}
.cr-hero-label {{ display: flex; align-items: center; gap: 10px; font-size: 14px; color: #D8E4DA; }}
.cr-verdict {{ font-size: 44px; line-height: 1.12; font-weight: 600; letter-spacing: -0.02em; margin: 14px 0 12px; color: {SAND_50}; max-width: 22em; }}
.cr-verdict em {{ font-style: normal; color: {ACCENT}; }}
.cr-run {{ font-size: 15px; color: #D8E4DA; }}
.st-key-hero .stButton button {{ background: transparent; color: {SAND_50}; border: 1px solid rgba(255,253,248,.35); }}
.st-key-hero .stButton button[kind="primary"] {{ background: {SAND_50}; color: {GREEN}; border: 0; }}

/* Metric tiles */
.cr-tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
.cr-tile {{ background: {SAND_50}; border-radius: 16px; padding: 16px 18px; box-shadow: 0 1px 2px rgba(60,45,20,.08); }}
.cr-tile .k {{ font-size: 14px; color: {INK_MUTED}; }}
.cr-tile .v {{ font-size: 28px; font-weight: 600; letter-spacing: -0.02em; margin: 6px 0 4px; direction: ltr; unicode-bidi: isolate; }}
.cr-tile .v small {{ font-size: 14px; font-weight: 500; color: {INK_MUTED}; margin-inline-start: 4px; }}
.cr-tile .v.water {{ color: {SKY_700}; }}
.cr-tile .n {{ font-size: 13px; color: {INK_MUTED}; line-height: 1.35; }}

/* Crop calendar */
.cr-cal {{ width: 100%; border-collapse: separate !important; border-spacing: 5px !important; border: 0 !important; }}
.cr-cal th, .cr-cal td, .cr-table th, .cr-table td {{ border-left: 0 !important; border-right: 0 !important; border-top: 0 !important; background: none; }}
.cr-cal td, .cr-cal th {{ border-bottom: 0 !important; }}
.cr-cal tr, .cr-table tr {{ background: none !important; border: 0 !important; }}
.cr-cal th {{ font-size: 13px; font-weight: 500; color: {INK_MUTED}; text-align: center; padding: 4px 0; }}
.cr-cal td.crop {{ font-size: 15px; white-space: nowrap; padding-inline-end: 12px; text-align: start; }}
.cr-cal td.cell {{ height: 34px; border-radius: 8px; text-align: center; font-weight: 700; font-size: 14px; min-width: 38px; }}
.cr-legend {{ display: flex; gap: 14px; align-items: center; font-size: 14px; flex-wrap: wrap; }}
.cr-legend i {{ display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 6px; font-style: normal; font-weight: 700; font-size: 12px; margin-inline-end: 6px; }}

/* Setup comparison table */
.cr-table {{ width: 100%; border-collapse: collapse; font-size: 15px; border: 0 !important; }}
.cr-table th {{ font-size: 13px; font-weight: 500; color: {INK_MUTED}; text-align: start; padding: 10px 12px; border-bottom: 1px solid {SAND_300}; }}
.cr-table td {{ padding: 14px 12px; border-bottom: 1px solid {SAND_200}; vertical-align: middle; }}
.cr-table tr.rec td {{ background: {GREEN_50}; }}
.cr-table tr.rec td:first-child {{ border-start-start-radius: 12px; border-end-start-radius: 12px; }}
.cr-table tr.rec td:last-child {{ border-start-end-radius: 12px; border-end-end-radius: 12px; }}
.cr-table .num {{ direction: ltr; unicode-bidi: isolate; white-space: nowrap; }}
.cr-table .strong {{ font-weight: 700; }}
.cr-swatch {{ display: inline-block; width: 22px; height: 0; border-top-width: 3px; vertical-align: middle; margin-inline-end: 8px; }}
.cr-bar {{ display: inline-block; width: 90px; height: 6px; border-radius: 3px; background: {SAND_200}; vertical-align: middle; margin-inline-start: 8px; overflow: hidden; }}
.cr-bar b {{ display: block; height: 100%; border-radius: 3px; }}

/* Home */
.cr-home-hero {{ padding: 40px 0 8px; }}
.cr-home-hero h1 {{ font-size: 56px; line-height: 1.05; font-weight: 600; letter-spacing: -0.025em; margin: 18px 0; }}
.cr-home-hero p.lead {{ font-size: 19px; color: #4A5247; max-width: 32em; }}
.cr-value {{ background: {SAND_50}; border-radius: 20px; padding: 24px; height: 100%; box-shadow: 0 1px 2px rgba(60,45,20,.08); }}
.cr-value .n {{ width: 36px; height: 36px; border-radius: 10px; background: {GREEN_50}; color: {GREEN}; display: grid; place-items: center; font-weight: 700; }}
.cr-value h3 {{ font-size: 18px; margin: 14px 0 6px; }}
.cr-value p {{ font-size: 15px; color: #4A5247; margin: 0; }}

/* Plan page */
.st-key-card_form {{ padding: 24px; }}
.cr-site {{ background: {SAND_100}; border: 1px solid {SAND_300}; border-radius: 14px; padding: 14px 16px; display: flex; gap: 12px; align-items: flex-start; }}
.cr-site .pin {{ width: 18px; height: 22px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); background: {SAND_400}; margin-top: 2px; flex: none; }}
.cr-site.on .pin {{ background: {GREEN}; }}
.st-key-priority [role="radiogroup"] label {{ background: {SAND_50}; border: 1px solid {SAND_300}; border-radius: 12px; padding: 10px 14px; width: 100%; margin-bottom: 8px; }}
.st-key-priority [role="radiogroup"] label:has(input:checked) {{ background: {GREEN_50}; border-color: {GREEN}; }}
iframe {{ border-radius: 20px; }}

/* Compare */
.cr-site-card {{ background: {SAND_50}; border-radius: 20px; overflow: hidden; box-shadow: 0 1px 2px rgba(60,45,20,.08); }}
.cr-site-card .head {{ padding: 20px 24px; }}
.cr-site-card .stats {{ display: grid; grid-template-columns: 1fr 1fr; border-top: 1px solid {SAND_300}; border-bottom: 1px solid {SAND_300}; }}
.cr-site-card .stats > div {{ padding: 18px 24px; }}
.cr-site-card .stats > div + div {{ border-inline-start: 1px solid {SAND_300}; }}
.cr-site-card .big {{ font-size: 30px; font-weight: 600; direction: ltr; unicode-bidi: isolate; }}
.cr-site-card .rec {{ padding: 20px 24px; }}
.cr-site-card .rec.green {{ background: {GREEN}; color: {SAND_50}; }}
.cr-site-card .rec.sky {{ background: {SKY_50}; color: {SKY_700}; }}
.cr-site-card .rec.none {{ background: {IMPOSSIBLE_FILL}; color: #5A1A12; }}
.cr-site-card .rec .v {{ font-size: 22px; font-weight: 600; line-height: 1.3; margin-top: 6px; }}
.cr-site-card .rows {{ padding: 8px 24px 20px; }}
.cr-site-card .row {{ display: flex; justify-content: space-between; gap: 12px; padding: 12px 0; border-bottom: 1px solid {SAND_200}; font-size: 15px; }}
.cr-site-card .row b {{ direction: ltr; unicode-bidi: isolate; }}
.cr-strip {{ background: #212A24; color: {SAND_50}; border-radius: 20px; padding: 32px 24px; height: 100%; display: flex; flex-direction: column; justify-content: center; text-align: center; gap: 10px; }}
.cr-strip .dots {{ color: {HEAT_2}; letter-spacing: 4px; font-size: 18px; }}
.cr-strip h3 {{ color: {SAND_50}; font-size: 22px; margin: 0; text-align: center; }}
.cr-strip p {{ color: #CFC9BA; font-size: 14px; margin: 0; text-align: center; }}

/* Sources list */
.cr-src {{ padding: 12px 0; border-top: 1px solid {SAND_300}; display: flex; justify-content: space-between; gap: 12px; }}
.cr-src a {{ font-weight: 600; }}

/* Chat dialog */
[data-testid="stChatMessage"] {{ background: {SAND_50}; border-radius: 16px; }}
div[role="dialog"] {{ border-radius: 20px; }}

@media (max-width: 1100px) {{
  .block-container, [data-testid="stMainBlockContainer"] {{ padding: 0 16px 64px; }}
  .st-key-topbar {{ margin: 0 -16px 16px !important; padding: 8px 16px; width: calc(100% + 32px) !important; }}
  .st-key-topbar [data-testid="stHorizontalBlock"] {{ flex-direction: row !important; flex-wrap: wrap !important; gap: 4px !important; }}
  .st-key-topbar [data-testid="stColumn"] {{ width: auto !important; flex: 0 0 auto !important; min-width: 0 !important; }}
  .st-key-topbar [data-testid="stColumn"]:first-child {{ flex-basis: 100% !important; }}
  [data-testid="stPageLink"] a {{ padding: 4px 8px; }}
  .cr-brand {{ margin-bottom: 6px; }}
  .cr-brand .mark {{ width: 28px; height: 28px; }}
  .cr-verdict {{ font-size: 30px; }}
  .cr-home-hero h1 {{ font-size: 38px; }}
}}
</style>
"""
