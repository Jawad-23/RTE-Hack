# Project plan: Farming the Desert Sun

Sep 25, 2026 · @Blay

**Status (Sep 26, 2026):** everything below is merged on `main` and deployed from it to https://croptions.streamlit.app. For how it works today, see [System architecture](07-architecture.md). The original schedule and pitch below are planning targets, not evidence of completion.

## 1. Goal and deliverables

**By Saturday's judging, demo a working web app: drop a pin and get back the best crop, setup, solar size and payback, with every number traceable to open data.**

We submit four things:

1. **Working prototype:** a web app that runs live, not slides pretending to be an app.
2. **Public GitHub repo** ([Jawad-23/RTE-Hack](https://github.com/Jawad-23/RTE-Hack)): MIT license, clean code, README, credits for all data and libraries.
3. **Pitch deck:** about 6 slides, problem to solution to demo to impact.
4. **Demo video (backup):** a 2-minute screen recording in case the live demo fails. The Croptions Kit page with the hidden simulator (`/kit-simulator`) is built for this; the readings CSV drives the 3D video.

## 2. Scope

**Build the must-haves first and demo them end to end before touching anything else.** Stretch items only start once the full pipeline works.

### Stage 1: the core planner (core on main; redesign and updates on this branch)

| Priority | Feature | Why | Status |
| --- | --- | --- | --- |
| Must-have | Pin on map (or typed coordinates), fetch NASA POWER data | Everything depends on it | Working; live NASA fetch still to be tested on a laptop |
| Must-have | Crop check: which crops fit which months | Challenge 1 feature: site suitability | Working |
| Must-have | Cooling simulation for 7 setups (8,760 hours) | Our unique insight | Working |
| Must-have | Solar sizing and payback for each setup | Challenge 1 feature: investment planning | Working, on estimated costs |
| Must-have | Results screen with recommendation and comparison table | What judges see | Working |
| Must-have | LLM explanation with number checker | Responsible AI criterion | Working; needs an API key to test live |
| Stretch | Chat follow-ups ("what if I double the budget?") | Shows the agent re-running tools | Working (same agent) |
| Must-have | Look and feel of the Croptions prototype (5 pages, English/Arabic, phone width) | What judges see first | Done on `jawad/redesign` |
| Stretch | Compare two sites side by side | The "same heat, different air" demo moment | Done on `jawad/redesign` |

### Stage 2: smarter shading and dust (implemented on this branch)

These steps are merged on `main`. The detailed completion record and scientific limitations are in [Optional update](05-optional-update.md).

| Step | Feature | Owner | Status |
| --- | --- | --- | --- |
| 1 | Split sunlight into growth light (PAR), heat (NIR) and UV | Me | Implemented; hourly parameters and units checked live |
| 2 | Humidity stress (VPD) and inside humidity per setup | Me + Mustafa (crops.csv column) | Implemented |
| 3 | Light sufficiency (daily light integral) so shading has a trade-off | Me + Mustafa | Implemented |
| 4 | Three new setups: NIR-screen wet pad, fixed agrivoltaic, agrivoltaic louvers | Me + Mustafa (CSV rows, electricity revenue) | Implemented |
| 5 | One shared rule-based screen controller | Me | Implemented |
| 6 | Operate simulator for the demo video | Me | Implemented; `planner/operate.py` is kept and tested, its page was replaced by the Croptions Kit |
| 7 | Dust: haze light loss, cleaning interval, dust-storm exposure (Open-Meteo) | Me + Mustafa | Implemented: recent 30-day exposure plus separate cleaning scenarios |
| 8 | Area scan (draw a rectangle, grid of plans) | Me | Implemented (max 25 points) |
| 9 | Wire new metrics through app, agent, checker, i18n, README | Everyone | Implemented |
| 10 | Croptions Kit (simulated): hidden simulator, live dashboard, thermal grid, CSV, kit cost; NASA climate card on Results | Me | Implemented ([details](06-croptions-kit.md)) |
| 11 | Results hub: assistant summary, investment scenarios (NPV, IRR, break-even), PVGIS solar, 7-day forecast, compare a second site | Me | Implemented |

### Not in scope (roadmap only; mention in the pitch, do not build)

Cameras, ESP32 and any other hardware; live sensors and spectrometers; learned (RL) controller; computer-vision dust detection; camera-based canopy stress detection; predictive maintenance; upwind dust-front warning; predictive pre-cooling; generative facility layouts; satellite imagery; SMS delivery; soil sensors; the 2040 climate view. See the roadmap in the [Problem and solution](01-problem-and-solution.md#8-roadmap-plan--build--operate) tab.

Keep the demo to about 8 crops and Qatar sites, but never hard-code Qatar: any pin on Earth should run.

## 3. Modules

**Each module is a plain Python function with a fixed input and output, so people can build them in parallel.** The interfaces live in `planner/schemas.py` and the [Team tasks](03-team-tasks.md#3-shared-contracts) tab; extend them, never rename.

| # | Module | Input | Output | Status |
| --- | --- | --- | --- | --- |
| 1 | `climate.py` | lat, lon | Hourly table: temp, humidity, solar radiation, wind (typical year) | Working |
| 2 | `crops.py` | climate table, crop list | For each crop, which months it can grow in open field | Working |
| 3 | `cooling.py` | climate table, crop heat limit, setup | Inside temperature per hour, coverage % | Working |
| 4 | `solar.py` | climate table, cooling energy needed | Panel size (kW), yearly solar output | Working |
| 5 | `economics.py` | setup, crop, farm size, prices | Build cost, running cost, profit per year, payback | Working |
| 6 | `optimizer.py` | pin, area, budget, priority, crop | Ranked plan (JSON-safe) | Working |
| 7 | `agent.py` + `checker.py` | user question + current plan | Checked plain-language answer; may re-run the planner | Working (needs an API key) |
| 8 | `controller.py` | one hour of climate + crop + screen state | Screen position % + reason code | Implemented |

### Core formulas

Wet-bulb temperature (Stull 2011), with T in °C and RH in %:

```math
T_w = T\arctan\left(0.151977\sqrt{RH + 8.313659}\right) + \arctan(T + RH) - \arctan(RH - 1.676331) + 0.00391838\,RH^{3/2}\arctan(0.023101\,RH) - 4.686035
```

Inside temperature of a wet-pad greenhouse, with pad efficiency η about 0.8 and solar heat gain ΔT about 3–5°C:

```math
T_{in} = T - \eta\,(T - T_w) + \Delta T_{solar}
```

Coverage, the key decision number:

```math
\text{Coverage} = \frac{\text{hours with } T_{in} < T_{crop\,limit}}{\text{growing hours}} \times 100\%
```

Solar size, with peak sun hours PSH and performance ratio PR about 0.8:

```math
P_{kW} = \frac{E_{cooling,\,daily}}{PSH \times PR}
```

Payback:

```math
\text{Payback (years)} = \frac{\text{Build cost}}{\text{Yearly revenue} - \text{Yearly running cost}}
```

Decision rule: pick the setup with the highest 10-year profit among those with coverage of at least 90%. If none reaches 90%, recommend a more heat-tolerant crop.

## 4. Team roles

**Three people, three layers.** Full step-by-step instructions are in the [Team tasks](03-team-tasks.md) tab.

| Person | Owns |
| --- | --- |
| Me (repo owner) | Repo, data pipeline, cooling physics, controller, optimizer, main app, simulator page |
| Salih | AI agent, number checker, English/Arabic chat, Arabic translations |
| Mustafa | Data tables and their sources, crop check, solar sizing, economics, README credits |

Stage 1 code for Salih's and Mustafa's layers was written for them on their own branches (`salih/agent-chat`, `mustafa/core-modules`) so the app runs end to end. Each of them should review their branch before it is merged.

## 5. Timeline

**Friday builds the engine; Saturday polishes, freezes code and rehearses.** Times assume judging on Saturday afternoon; shift everything once we confirm the real deadline from the Participant Handbook.

| When | Milestone | Checkpoint | Status |
| --- | --- | --- | --- |
| Fri 09:00–10:00 | Kickoff: agree module interfaces, create repo, add MIT license | Repo public, everyone can push | Done (public visibility still to set) |
| Fri 10:00–13:00 | Each role builds its module on fixed test data | Each module runs alone in the terminal | Done |
| Fri 13:00–14:00 | Lunch + mentor check-in on Slack | Feedback noted | |
| Fri 14:00–17:00 | Connect modules: pin to data to cooling to payback | **Full pipeline prints a plan in the terminal** | Done (`python -m planner.optimizer`) |
| Fri 17:00–21:00 | Streamlit app with map and results screen; agent + number checker | Pin to results screen works in the browser | Done; merge branches into `main` |
| Fri 21:00–23:00 | Stage 2 steps 1–3 if the pipeline is solid; draft slides | Deck skeleton done | |
| Sat 08:00–10:00 | Bug fixes, test 5 different pins, README | App works on every test pin | |
| Sat 10:00 | **Code freeze.** No new features after this | Final commit tagged | |
| Sat 10:00–11:00 | Record backup demo video | Video saved | |
| Sat 11:00–13:00 | Finish deck, rehearse the pitch 3 times with a timer | Pitch fits the time limit | |
| Sat afternoon | Submit and present | Submitted | |

The one rule that matters: if the full pipeline is not working by Friday 17:00, drop all stretch items and make the must-haves solid.

## 6. Repo structure and stack

**One repo, one folder per layer, all assumptions in editable CSV files.** Anyone in another country can swap in local prices and crops without touching code.

```
RTE-Hack/
├── app.py                  # entry: top bar, navigation, language, assistant dialog
├── views/                  # pages: home, plan, results, compare, assumptions
├── ui/                     # theme (design tokens, CSS), components, charts, state, insights
├── .streamlit/config.toml  # theme colours
├── assets/logo.svg
├── planner/
│   ├── schemas.py          # shared names, units, constants
│   ├── climate.py          # NASA POWER fetch + typical year + cache
│   ├── crops.py            # crop-by-month check
│   ├── cooling.py          # wet-bulb + 8,760-hour simulation
│   ├── solar.py            # panel sizing
│   ├── economics.py        # cost, profit, payback
│   ├── optimizer.py        # every crop × setup, filter, rank: plan()
│   ├── controller.py, agronomy.py, water.py, dust.py, market.py, scan.py, operate.py
│   ├── site_climate.py     # the "What NASA measured" card
│   ├── finance.py          # NPV, IRR, break-even, downside cases
│   ├── site_data.py        # PVGIS, Open-Meteo forecast, World Bank rates
│   ├── kit.py              # Croptions Kit: readings, CWSI/VPD, advice, costs, KitStore
│   ├── agent.py            # LLM agent with tools (OpenRouter, Claude or local)
│   ├── checker.py          # blocks numbers not in the plan
│   └── chat_ui.py          # English/Arabic chat panel
├── i18n/                   # en.json, ar.json, t()
├── styles/rtl.css          # right-to-left layout for Arabic
├── data/
│   ├── crops.csv           # heat limits, yield, VPD/DLI, FAO-56 crop coefficients
│   ├── kit_scenarios.csv   # Croptions Kit simulator scenarios (estimates)
│   ├── snapshots/          # offline copy of FAOSTAT prices (planner/market.py)
│   ├── setups.csv          # build/running costs and cooling parameters
│   ├── settings.csv        # electricity, solar cost, performance ratio
│   ├── demo_sites.csv      # example pins (Al Khor, Al Karaana)
│   └── cache/              # NASA climate, FAOSTAT, countries, site/ (PVGIS, forecast, World Bank); not committed
├── tests/                  # one test file per module
├── docs/                   # these planning docs
├── ui-demo/                # Croptions UI prototype
├── README.md               # problem, how to run, credits
└── LICENSE                 # MIT
```

Pages live in `views/` (not `pages/`, because the app uses its own top navigation): home, plan, results, compare, operate (the Croptions Kit, `/kit`), assumptions and the hidden kit simulator `kit_remote.py` (`/kit-simulator`). Full detail: [System architecture](07-architecture.md).

| Layer | Tool |
| --- | --- |
| Language | Python 3.11 |
| App and map | Streamlit, folium (Leaflet), Plotly |
| Physics | PsychroLib (Stull formula as fallback), NumPy, pandas |
| Data | NASA POWER API, FAOSTAT producer prices (live, with offline snapshot), FAO-56 water use, FAO EcoCrop, Nominatim, Open-Meteo Air Quality and forecast, EU JRC PVGIS, World Bank |
| AI agent | The deployed app uses free open models on OpenRouter (OpenAI-compatible API, temperature 0.4, fallback model list). Claude (`claude-sonnet-5`, no temperature sent) and local models (Ollama) also work. Either way the number checker keeps answers grounded |
| Hosting for demo | Streamlit Community Cloud (free) |

## 7. Demo script and pitch flow

**The wow moment is two pins at the same temperature getting opposite answers.** Build the whole pitch toward it.

| Time | Slide or screen | What we say |
| --- | --- | --- |
| 0:00–0:30 | Problem slide | "Qatar imports about 85% of its food. The problem isn't too little sun; it's too much heat." |
| 0:30–1:00 | Three decisions slide | What to grow, what setup, will it pay off: today all guesswork. |
| 1:00–1:45 | **Live demo, pin 1: dry inland site** | Tool recommends a cheap wet-pad greenhouse; high coverage. |
| 1:45–2:30 | **Live demo, pin 2: humid coastal site, same temperature** | Tool rejects wet pads, recommends a solar-powered chiller, shows payback. "A thermometer can't tell you this. Our tool can." |
| 2:30–3:00 | Ask the agent a follow-up | "What if my budget is half?" The agent re-runs the tools and gives a new plan. |
| 3:00–3:30 | Responsible AI slide | "Our AI plans and explains, but it cannot make up a number." |
| 3:30–4:00 | Impact slide | Open source, works anywhere hot and dry, SDGs 2, 6, 7 and 13. |

Pick and test both demo pins on Friday night, and screenshot the results in case the internet fails.

## 8. Risks and fallbacks

**Every risk has a fallback decided now, so nobody panics on Saturday.**

| Risk | Fallback |
| --- | --- |
| NASA POWER is slow or down during the demo | Cache the data for both demo pins as local files on Friday. Offline, the app now fails in seconds with a clear message instead of hanging |
| Venue Wi-Fi fails or the map can't load | Run the app locally; use **Or type coordinates** under the map; backup video as last resort |
| LLM API fails, is slow, or no key | The chat says it is unavailable; the full plan and dashboard still work. An open-source model on a laptop (Ollama) needs no internet at all |
| Cost and price numbers are rough | Labelled "estimate" in the CSVs and in the app; judges value honesty. Quote only the app's numbers in the pitch |
| The chiller payback on estimated costs is long | This may undercut the pitch's "solar chiller pays off" story. Replace estimates with sourced costs before building slides around it |
| Crop heat limits are hard to find | Start with 8 well-known crops typed in by hand from EcoCrop; mark each value's source |
| Someone builds hardware tonight | Cameras and ESP32 are roadmap only; the Croptions Kit simulator stands in for them in the demo |
| Running out of time | Drop stretch features at Friday 17:00, never the must-haves |

## 9. Submission checklist

**Tick these off before the code freeze; open-source rules are a hard requirement.**

- [x] MIT license from the first code commit
- [x] Repo is public
- [x] Every library and dataset credited in the README
- [ ] Every value in `data/*.csv` has a real source, or is clearly labelled `estimate`
- [ ] README covers the problem, how to run, architecture diagram, data sources and limits
- [x] Demo pins tested with live NASA data and cached locally (see validation report)
- [ ] Backup demo video recorded
- [ ] Pitch deck final and rehearsed with a timer
- [ ] Submitted in the format the Participant Handbook asks for

### Open questions

- [ ] What is the exact submission deadline and format? Check the Participant Handbook QR code.
- [ ] What does the academic integrity policy say about using AI assistants? Much of the code was written with Claude Code.
- [ ] How long is the pitch? Adjust the demo script to fit.
- [ ] Which five regions go in "Where this applies"?
- [ ] Does the team agree that cameras and ESP32 are roadmap only?

## 10. Known gaps: what is not real yet

**Everything the app shows is calculated, but some inputs are estimates and some APIs have never been called live.** Keep this list current; judges will ask.

### APIs: missing or never run live

| API / data | State | What it takes |
| --- | --- | --- |
| NASA POWER hourly (temperature, humidity, sunlight, wind) | Implemented and checked against the live public API; see validation report | Run `python -m planner.climate 25.29 51.53` on a laptop |
| Claude API | Code written and tested with a fake model; **never called live** | An `ANTHROPIC_API_KEY` in `.env` |
| Open-source LLM through OpenRouter (free models) | Code written and tested against a fake OpenAI-compatible server, including reading the key from Streamlit Secrets; **never called live** (OpenRouter is blocked in the build environment) | Add the OpenRouter key to the app's Secrets and ask the chat a question |
| Map (Leaflet scripts and OpenStreetMap tiles) | Not loaded in the build environment; typed coordinates work | A normal internet connection |
| FAO EcoCrop | **No download or API.** Crop limits in `crops.csv` were typed in as estimates | Look up each crop and fill `source` |
| FAOSTAT | **Live.** Latest farm-gate price for the pin's country (`planner/market.py`), with a committed snapshot used when it is newer than 30 days or FAOSTAT is unreachable. Qatar has 2023 prices for 7 of 8 crops; strawberry is scaled from world prices | Refresh the snapshot before the demo: `python -m planner.market --refresh-snapshot` |
| NASA POWER spectral data (PAR, UV, longwave, clear-sky) | Implemented and checked live | |
| Open-Meteo Air Quality (dust) | Implemented for recent modelled dust exposure | |
| Open-Meteo Climate API (2040/2050 view) | Not built (stretch) | |
| Nominatim search (place name → coordinates) | Built on the Plan page ("Search by place name"); reverse lookup gives the country for prices | |
| EU JRC PVGIS, Open-Meteo 7-day forecast, World Bank lending rate and inflation | Implemented with recorded-response tests; **never called live from the build environment** (blocked there). Each is optional: a failure hides its card or uses the 4 % fallback rate, and the service is skipped for 15 minutes | Open Results on the deployed app and check the "Sun, heat and humidity" card and the investment note |

### Numbers that are estimates (all in `data/*.csv`, all labelled `estimate`)

- **`setups.csv`, the numbers that decide the winner:** build cost per m² (open field 10, shade net 40, wet pad 300, chiller 450 QAR), running cost per m², yield factor per setup (1.0 to 1.8), extra water per m², and the physics values: shade net cools by 2 °C, pad efficiency 0.8, greenhouse solar heat gain 4 °C, chiller setpoint 26 °C, chiller load 0.03 kW per m² per °C, COP 3.
- **`settings.csv`:** solar cost 2,500 QAR/kW, electricity 0.13 QAR/kWh, performance ratio 0.8, risky margin 3 °C.
- **`crops.csv`:** temperature limits and yields for all 8 crops (crop coefficients come from FAO-56 Table 12, prices from FAOSTAT and water from the FAO-56 calculation, so those are no longer estimates).

### Simplifications in the code

1. **Solar and night-time cooling:** corrected on this branch. Hourly deficits incur grid costs; surplus export defaults to zero revenue. Grid access is assumed, with no battery.
2. **Electricity tariffs:** now applied to hourly grid imports; confirm the local tariff and any export agreement before investment.
3. **Air pressure is fixed at sea level** (101,325 Pa) for wet-bulb; high sites are slightly off.
4. **Greenhouse solar heat gain is on/off:** the full 4 °C whenever the sun is up, not scaled by how strong it is.
5. **Wet pads:** efficiency is constant; pad water now follows the weather (`planner/water.py`). If the country lookup (Nominatim) fails, prices fall back to world medians and the source line says so.
6. **Revenue** = yield × price × (growing months ÷ 12) × setup yield factor. Heat stress within a growing month is not modelled as a yield curve. DLI now gates suitability; the optional soiling scenario applies an estimated light/yield factor. A growing month is one with at least 90 % of hours below the crop's limit.
7. **Coverage only checks the crop's maximum temperature**, over all 8,760 hours. Cold winter nights inside a greenhouse are not checked.
8. **Economics:** payback and 10-year profit are undiscounted; the investment table discounts at a real rate (World Bank, else 4 %). No panel degradation, labour, land, financing or equipment replacement. The budget only limits build cost.
9. **Typical year:** averaging 5 years smooths out heatwaves, so extremes are under-represented.
10. **Arabic:** most labels come from the designer's prototype; the ones added for the app (chat, charts, compare) were written without a native speaker and need review.
11. **Prototype features not built:** editing assumptions inside the app (values are read-only; edit `data/*.csv`), PDF export (the app downloads the plan as JSON) and the offline/error preview toggles.
12. **Croptions Kit:** no hardware. Readings come from the hidden simulator and live in server memory (lost on restart). CWSI coefficients, alert limits and kit prices are estimates; no yield gain from the kit is assumed.

What is **not** faked: the app never uses made-up climate data. The synthetic climate years exist only in `tests/`.
