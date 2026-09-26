"""Record a start-to-finish demo video of Croptions with a real browser.

    pip install playwright imageio-ffmpeg
    python -m playwright install chromium
    python scripts/record_demo.py                                # the live site
    python scripts/record_demo.py --url http://localhost:8501    # a local run

Walks through Home -> Try Al Khor -> Results (verdict, assistant, Kit card, investment, NASA card,
calendar, setups, charts) -> a question to the assistant -> Plan -> Compare sites -> Croptions Kit with the
phone simulator (Heat stress, Approve) and the one-day smart-screen simulation -> Arabic. Captions are drawn
on the page. Writes <out>/croptions-demo.mp4 (plus the raw .webm clips).

Set CHROMIUM_PATH to use a specific Chromium build. Tips: run it once first so NASA data for Al Khor is cached and the recording has no long wait.
--no-chat skips the assistant question (use it when no LLM key is set). --preview adds a banner saying
the run used test data.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

SIZE = {"width": 1280, "height": 720}
PHONE = {"width": 390, "height": 780}
SAND = "F5F0E6"

OVERLAY_JS = """
([text, preview]) => {
  let c = document.getElementById('demo-caption');
  if (!c) {
    const style = document.createElement('style');
    style.textContent = `#demo-caption{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:999999;
      background:rgba(18,56,38,.94);color:#FFFDF8;font:600 22px/1.35 "IBM Plex Sans",system-ui,sans-serif;padding:12px 22px;
      border-radius:14px;max-width:80%;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.25);transition:opacity .35s}
      #demo-caption:empty{opacity:0}
      #demo-ribbon{position:fixed;right:12px;top:78px;z-index:999999;background:#FBEBC8;color:#7A5200;font:600 13px system-ui;
      padding:6px 12px;border-radius:999px}
      @media (max-width:500px){#demo-caption{font-size:15px;bottom:14px;padding:8px 12px;max-width:92%}
        #demo-ribbon{top:8px;font-size:11px}}
      .demo-ring{outline:4px solid #E9B92F!important;outline-offset:3px;border-radius:12px;transition:outline .2s}`;
    document.head.appendChild(style);
    c = document.createElement('div'); c.id = 'demo-caption'; document.body.appendChild(c);
  }
  if (preview && !document.getElementById('demo-ribbon')) {
    const r = document.createElement('div'); r.id = 'demo-ribbon';
    r.textContent = 'Preview recorded with test weather, not real site data'; document.body.appendChild(r);
  }
  c.textContent = text;
}
"""


class Demo:
    def __init__(self, page: Page, preview: bool, pace: float):
        self.page, self.preview, self.pace = page, preview, pace
        self.t0 = time.monotonic()

    def now(self) -> float:
        return time.monotonic() - self.t0

    def wait(self, seconds: float) -> None:
        self.page.wait_for_timeout(int(seconds * 1000 * self.pace))

    def say(self, text: str, hold: float = 0) -> None:
        self.page.evaluate(OVERLAY_JS, [text, self.preview])
        if hold:
            self.wait(hold)

    def scroll_to(self, selector: str, hold: float = 3.5) -> bool:
        loc = self.page.locator(selector).first
        if not loc.count():
            return False
        loc.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'start'})")
        self.wait(hold)
        return True

    def scroll_by(self, pixels: int, hold: float = 1.5) -> None:
        self.page.evaluate("""(px) => { const m = document.querySelector('[data-testid="stMain"]') || document.scrollingElement;
                               m.scrollBy({top: px, behavior: 'smooth'}); }""", pixels)
        self.wait(hold)

    def click(self, locator, hold: float = 1.0) -> None:
        loc = locator.first
        loc.scroll_into_view_if_needed()
        loc.evaluate("el => el.classList.add('demo-ring')")
        self.wait(0.9)
        loc.click()
        self.wait(hold)


def record(url: str, out: Path, chat: bool, preview: bool, pace: float) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    marks = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        ctx = browser.new_context(viewport=SIZE, record_video_dir=str(out), record_video_size=SIZE)
        page = ctx.new_page()
        d = Demo(page, preview, pace)
        page.goto(url, wait_until="networkidle")
        page.locator("text=Turn desert sun").first.wait_for(timeout=60000)
        marks["start"] = d.now()

        # ---------- Home ----------
        d.say("Croptions: an AI farm planner for hot, dry regions", 3.5)
        d.scroll_by(650, 2.5)
        d.say("It checks the site, recommends a crop and setup, and prices the investment", 3)
        d.scroll_by(700, 3)
        d.say("The Croptions Kit then watches the crop on the farm", 3)
        d.scroll_by(-3000, 1.5)
        d.say("One click: try a real site on Qatar's coast")
        d.click(page.get_by_role("button", name=re.compile("Try Al Khor")), 0.5)
        d.say("Five years of hourly NASA weather · 8 crops × 7 setups = 56 options")
        page.locator(".st-key-hero, .st-key-hero_none").first.wait_for(timeout=240000)
        page.locator(".st-key-card_chat [data-testid='stChatMessage']").first.wait_for(timeout=120000)
        d.wait(1)

        # ---------- Results ----------
        d.say("The recommendation, with its payback, from our own calculations", 4)
        d.scroll_to(".cr-tiles", 3.5)
        d.say("Heat coverage, build cost, profit, payback, water and solar", 1)
        d.scroll_to(".st-key-card_chat", 1)
        d.say("The assistant explains the plan; every number it writes is checked", 4.5)
        d.say("The Croptions Kit: cost and payback with sensor pods added", 3.5)
        if d.scroll_to(".st-key-card_invest", 1):
            d.say("Investment view: NPV, IRR, break-even crop price and a downside case", 4.5)
        if d.scroll_to(".st-key-card_site", 1):
            d.say("What NASA measured at this exact site", 3)
            d.scroll_by(420, 3)
        if d.scroll_to(".st-key-card_gis", 1):
            d.say("Terrain-aware solar from EU PVGIS and this week's forecast", 4)
        if d.scroll_to(".st-key-card_calendar", 1):
            d.say("Which crops can grow outdoors in which months", 3.5)
        if d.scroll_to(".st-key-card_compare", 1):
            d.say("All seven setups compared for the chosen crop", 4)
        if d.scroll_to(".st-key-card_temp", 1):
            d.say("Inside temperature of every setup against the crop's heat limit", 4)
        if d.scroll_to(".st-key-card_sources", 1):
            d.say("Every assumption and data source is shown", 3)

        # ---------- Ask the assistant ----------
        if chat:
            d.scroll_to(".st-key-card_chat", 1.5)
            d.say("Ask a what-if question in plain words")
            box = page.get_by_placeholder(re.compile("Ask about this plan"))
            box.first.click()
            box.first.type("What if my budget is half?", delay=int(60 * pace))
            d.wait(0.6)
            before = page.locator(".st-key-card_chat [data-testid='stChatMessage']").count()
            box.first.press("Enter")
            d.say("The assistant re-runs the real planner, then answers")
            try:
                page.wait_for_function(
                    "(n) => document.querySelectorAll('.st-key-card_chat [data-testid=\"stChatMessage\"]').length >= n + 2",
                    arg=before, timeout=120000)
            except Exception:
                pass
            d.scroll_to(".st-key-card_chat", 1)
            d.scroll_by(260, 5)

        # ---------- Plan ----------
        d.say("")
        d.click(page.locator(".st-key-topbar").get_by_role("link", name="Plan"), 2.5)
        d.say("Plan any pin on Earth: map, place search, size, budget, crop and priority", 5)

        # ---------- Compare sites ----------
        d.say("")
        d.click(page.locator(".st-key-topbar").get_by_role("button", name=re.compile("Menu")), 1)
        d.click(page.get_by_role("link", name=re.compile("Compare sites")), 2)
        d.say("Compare two sites with the same farm and budget")
        d.click(page.get_by_role("button", name=re.compile("^Compare")), 1)
        page.locator(".cr-strip").first.wait_for(timeout=240000)
        d.wait(1)
        d.scroll_to(".cr-strip", 0.5)
        d.say("Humidity changes which cooling works, even at the same heat", 5)

        # ---------- Croptions Kit ----------
        d.say("")
        d.click(page.locator(".st-key-topbar").get_by_role("link", name=re.compile("Croptions Kit")), 3)
        d.say("The Croptions Kit page gets a Kit ID for this farm", 3.5)
        code = page.locator(".cr-kit-id").first.inner_text().strip()
        marks["switch"] = d.now()

        phone_ctx = browser.new_context(viewport=PHONE, record_video_dir=str(out), record_video_size=PHONE,
                                        is_mobile=True, device_scale_factor=2)
        phone_page = phone_ctx.new_page()
        phone = Demo(phone_page, preview, pace)
        phone_page.goto(f"{url.rstrip('/')}/kit-simulator?farm={code}", wait_until="networkidle")
        phone_page.get_by_role("button", name=re.compile("Heat stress")).first.wait_for(timeout=60000)
        marks["phone_start"] = phone.now()
        phone.say("On a phone: the Kit simulator sends a reading", 3)
        phone.click(phone_page.get_by_role("button", name=re.compile("Heat stress")), 2.5)
        phone.say("A heat-stress reading is sent to the farm", 2.5)
        marks["phone_end"] = phone.now()
        marks["phone_video"] = phone_page.video.path()
        phone_ctx.close()

        page.bring_to_front()
        d.wait(3)
        marks["back"] = d.now()
        d.say("The reading arrives in about 2 seconds, tagged as a demo reading", 1)
        d.scroll_to(".cr-tiles", 4)
        d.say("Leaf and air temperature, humidity, light, crop water stress and mould risk", 4)
        approve = page.get_by_role("button", name=re.compile("Approve"))
        if approve.count():
            d.scroll_to(".st-key-card_kit_advice", 1.5)
            d.say("The kit advises the shade screen; the farmer approves", 1)
            d.click(approve, 3)
        if d.scroll_to(".st-key-card_kit_thermal", 1):
            d.say("Thermal view, alerts and a readings log for the farm", 4)
        exp = page.locator("[data-testid='stExpander'] summary", has_text=re.compile("one simulated day"))
        if exp.count():
            d.click(exp, 2)
            d.scroll_by(300, 1)
            d.say("One simulated day: fixed shade vs the kit's smart screen", 5)

        # ---------- Arabic ----------
        d.say("")
        d.click(page.locator(".st-key-topbar").get_by_role("link", name="Home"), 2)
        d.click(page.locator(".st-key-topbar").get_by_text("العربية", exact=True), 3)
        d.say("Full Arabic, right to left", 3.5)
        d.say("croptions.streamlit.app · Plan the farm. The Croptions Kit protects it.", 4)
        marks["end"] = d.now()
        marks["main_video"] = page.video.path()
        ctx.close()
        browser.close()
    return marks


def stitch(marks: dict, out: Path) -> Path:
    """Cut the browser clip at the Kit, insert the phone clip, and write one H.264 MP4."""
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    target = out / "croptions-demo.mp4"
    m = marks
    graph = (
        f"[0:v]trim=start={m['start']:.2f}:end={m['switch']:.2f},setpts=PTS-STARTPTS[a1];"
        f"[1:v]trim=start={m['phone_start']:.2f}:end={m['phone_end']:.2f},setpts=PTS-STARTPTS,"
        f"scale=-2:{SIZE['height'] - 40},pad={SIZE['width']}:{SIZE['height']}:(ow-iw)/2:(oh-ih)/2:color=0x{SAND}[b];"
        f"[0:v]trim=start={m['back']:.2f}:end={m['end']:.2f},setpts=PTS-STARTPTS[a2];"
        f"[a1][b][a2]concat=n=3:v=1:a=0,fps=25,format=yuv420p[v]"
    )
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(m["main_video"]), "-i", str(m["phone_video"]),
                    "-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                    "-movflags", "+faststart", str(target)], check=True)
    return target


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Record a Croptions demo video.")
    ap.add_argument("--url", default="https://croptions.streamlit.app")
    ap.add_argument("--out", default="demo-video")
    ap.add_argument("--no-chat", action="store_true", help="skip the assistant question (no LLM key set)")
    ap.add_argument("--preview", action="store_true", help="label the video as recorded with test data")
    ap.add_argument("--pace", type=float, default=1.0, help="1.0 = normal; 1.3 = slower")
    args = ap.parse_args()
    out_dir = Path(args.out)
    result = record(args.url, out_dir, chat=not args.no_chat, preview=args.preview, pace=args.pace)
    print(f"Saved {stitch(result, out_dir)} ({result['end'] - result['start'] - (result['back'] - result['switch']) + result['phone_end'] - result['phone_start']:.0f} s)")
