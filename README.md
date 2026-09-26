# RTE Hack: Farming the Desert Sun

Our project for the **Reboot the Earth** hackathon (Doha 2026, Challenge 1). Drop a pin anywhere hot and dry and the app tells you what to grow, what setup to build (seven setups including selective heat screens and agrivoltaics), how much solar to install and when it pays off. Every number comes from open data or an editable CSV.

## Run it

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then paste your own LLM key: OpenRouter by default, or Claude (never commit .env)
streamlit run app.py
```

Print a plan in the terminal without the app:

```bash
python -m planner.optimizer 25.29 51.53 --area 500 --budget 250000 --priority profit
```

Run the tests: `python -m pytest`

The first run for a new pin fetches 5 years of hourly data from NASA POWER (can take a minute) and caches it in `data/cache/`. If the map can't load, use **Or type coordinates** under it.

## Try the Croptions Kit

There is no hardware yet, so a hidden simulator page plays the kit. It is not linked anywhere in the app.

1. Open the app (for example https://croptions.streamlit.app), analyse a site, then open **✦ Croptions Kit** in the top bar (also in **☰ Menu**).
2. Note the 4-digit **Kit ID** at the top of the page.
3. In a second tab or on a phone, open the simulator with that ID:
   `https://croptions.streamlit.app/kit-simulator?farm=<Kit ID>`
   (locally: `http://localhost:8501/kit-simulator?farm=<Kit ID>`; a phone needs the Network URL Streamlit prints, not localhost).
4. Select a scenario: **Normal** (at the time of day you choose), **Heat stress**, **Dry air**, **Sun surge** or **Humid night**, or press **Stream the day** for one reading every two seconds from 05:00 to 20:00.
5. Back on the Kit page the reading appears within two seconds with leaf temperature, water stress (CWSI), air dryness (VPD), dew-point risk, alerts and the screen advice (Auto, Approve once or Manual). The Results page shows the latest reading in its Croptions Kit card.

Simulated readings are built from the site's NASA typical-year weather passed through the recommended setup. The Kit page tags each one **Demo reading · simulated**, the Results card says "Latest demo reading (simulated)", and the readings CSV marks every row `source = simulated`. At the bottom of the Kit page, **Fixed shade vs the kit's smart screen** simulates one day of the typical year: the kit benefit the app actually calculates.

## Layout

| Path | What | Owner |
| --- | --- | --- |
| `app.py` | Entry point: top bar, page navigation, language switch, the "Ask Croptions" dialog | Repo owner |
| `views/` | The six pages: Home, Plan, Results, Compare sites, Croptions Kit (Operate), Assumptions; plus the hidden kit simulator `kit_remote.py` (`/kit-simulator`) | Repo owner |
| `ui/` | Design tokens and CSS (`theme.py`), HTML components, Plotly charts, page state, chart summaries (`insights.py`) | Repo owner |
| `.streamlit/config.toml`, `assets/` | Theme colours and logo from the Croptions design system | Repo owner |
| `planner/schemas.py` | Shared column names, setups, statuses, units | Repo owner |
| `planner/climate.py` | NASA POWER fetch → 8,760-hour typical year, cached | Repo owner |
| `planner/cooling.py` | Wet-bulb physics and inside temperature per setup | Repo owner |
| `planner/optimizer.py` | Runs every crop × setup, filters, ranks: `plan()` | Repo owner |
| `planner/site_climate.py`, `planner/kit.py`, `ui/kit_ui.py` | NASA climate card on Results; the simulated Croptions Kit (readings, CWSI/VPD/dew point, advice, costs, simulator ↔ dashboard inbox) | Repo owner |
| `planner/finance.py`, `planner/site_data.py` | NPV, IRR, break-even price and downside cases; PVGIS solar, Open-Meteo 7-day forecast and World Bank rates | Repo owner |
| `planner/crops.py`, `solar.py`, `economics.py`, `data/*.csv` | Crop check, solar sizing, economics, data tables (`demo_sites.csv` holds the example pins) | Mustafa |
| `planner/agent.py`, `checker.py`, `chat_ui.py`, `i18n/`, `styles/rtl.css` | LLM agent (OpenRouter, Claude or a local model), number checker, English/Arabic chat | Salih |
| `planner/controller.py`, `agronomy.py`, `water.py`, `dust.py`, `scan.py`, `operate.py`, `market.py` | Screen rule, light/VPD checks, FAO-56 water, dust scenarios, area scan, one-day fixed-shade vs smart-screen simulation (a section on the Kit page), FAOSTAT prices | Repo owner / Mustafa |
| `tests/` | One test file per module | everyone |
| `docs/` | Problem, plan, team tasks, hackathon brief, Croptions Kit and the [system architecture](docs/07-architecture.md) ([start here](docs/README.md)) | |
| `ui-demo/` | Croptions UI prototype and design system the app is styled on (open `Croptions.dc.html`) | |

Crop prices come from FAOSTAT for the pin's country and water use is calculated from the site's weather. Crop limits, yields and equipment costs in `data/*.csv` are still estimates, and the app says so. Costs in particular decide which setup wins, so treat recommendations as illustrative until those rows have real sources.

## The AI assistant

The assistant runs on any LLM set in `.env` or the app's Secrets: free open models on OpenRouter (the deployed app), Claude, or a local model. On Results it opens with a summary of the plan; the **Ask Croptions** button opens the same conversation in a dialog. It has two tools that run our own planner (`run_plan`, `compare_sites`). A checker compares every number in the reply with the plan and tool results; an answer with an unknown number is rewritten once, then replaced by a template built only from plan fields. Without a model configured the chat says it is unavailable and the dashboard still works.

**Claude (default):** put `ANTHROPIC_API_KEY=...` in `.env`.

**Free open models through OpenRouter (recommended for the demo):** create a key at [openrouter.ai/keys](https://openrouter.ai/keys), then put these lines in `.env`, or on Streamlit Cloud in the app's **Settings → Secrets** (TOML: `LLM_API_KEY = "sk-or-..."`):

```
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3.8-27b:free
LLM_FALLBACK_MODELS=nvidia/nemotron-3-super-120b-a12b:free,openrouter/free
LLM_API_KEY=sk-or-...
```

Free models change often and have tight daily limits; `LLM_FALLBACK_MODELS` lets OpenRouter switch to the next one. If every request fails with "no endpoints found", allow free endpoints under OpenRouter **Settings → Privacy**.

**Open-source model instead:** any server with an OpenAI-compatible `/chat/completions` API works. For a local model with [Ollama](https://ollama.com):

```bash
ollama pull qwen2.5:7b-instruct
```

then in `.env`:

```
LLM_PROVIDER=openai_compatible
LLM_MODEL=qwen2.5:7b-instruct
LLM_BASE_URL=http://localhost:11434/v1
```

Hosted services such as Groq or OpenRouter work the same way with their base URL and `LLM_API_KEY`. Smaller models call tools less reliably; the checker still blocks any number they invent.

What is still estimated or untested: [docs/02-project-plan.md, section 10](docs/02-project-plan.md#10-known-gaps-what-is-not-real-yet).

## How we work

Branch per person and feature (`<owner>/<feature>`), only edit files you own, and open a pull request into `main`. Current branches and merge order: [docs/03-team-tasks.md](docs/03-team-tasks.md#branches-right-now). Full rules: [docs/03-team-tasks.md](docs/03-team-tasks.md#4-rules-for-everyone).

## Roadmap: Plan → Build → Operate

**Plan and Build are real calculations on open data; Operate is simulated.** On `main` today: spectral sunlight, humidity stress, daily light, seven setups, a rule-based screen controller, cleaning scenarios, a bounded area scan, FAOSTAT prices, FAO-56 water, investment scenarios (NPV, IRR, break-even, downside), PVGIS solar, a 7-day forecast and the Croptions Kit dashboard. How it all fits together: [docs/07-architecture.md](docs/07-architecture.md).

See [implementation, validation and remaining work](docs/05-optional-update.md). Run `python scripts/validate_demo.py --five-sites` to verify public data access and cache demo sites. The default planner now prices uncovered cooling electricity hour by hour; surplus solar earns zero by default. All new crop and equipment parameters remain illustrative estimates.

**Croptions Kit:** the Kit page shows live readings, crop water stress, alerts and screen advice in Auto, Approve-once or Manual mode. Until the hardware exists, readings come from the hidden simulator (see [Try the Croptions Kit](#try-the-croptions-kit)). See [docs/06-croptions-kit.md](docs/06-croptions-kit.md).

Future work only, none of it in the code:

- Learned (reinforcement learning) controller trained on our simulator
- Real Croptions Kit pods (thermal camera, ESP32) posting the same reading format the simulated kit uses
- Computer-vision dust detection and targeted cleaning
- Camera-based canopy stress detection
- Predictive maintenance (screen motors, panel soiling)
- Upwind dust-front early warning
- Predictive pre-cooling
- Generative facility layouts

## Where this applies

The planner runs on any pin on Earth. *(To fill: the five regions from the feasibility list.)*

## Credits

### Data

| Source | Used for | License / terms |
| --- | --- | --- |
| [NASA POWER](https://power.larc.nasa.gov/) | Hourly temperature, humidity, sunlight, wind | Free and open; credit "NASA Langley Research Center (LaRC) POWER Project" |
| [FAO EcoCrop](https://gaez.fao.org/pages/ecocrop) | Crop temperature limits (values in `data/crops.csv` are estimates until checked) | Open; credit FAO |
| [FAOSTAT](https://www.fao.org/faostat/en/#data/PP) | Crop prices: latest farm-gate price for the pin's country, downloaded automatically and refreshed monthly (`planner/market.py`); an offline copy is in `data/snapshots/` | CC BY 4.0; credit FAO |
| [FAO-56](https://www.fao.org/4/x0490e/x0490e00.htm) | Crop water use: hourly Penman-Monteith from the NASA POWER weather, times FAO crop coefficients (`planner/water.py`) | Credit FAO (Allen et al. 1998) |
| [OpenStreetMap Nominatim](https://nominatim.org/) | Which country the pin is in, for its prices | ODbL; credit OpenStreetMap contributors |
| [Open-Meteo / CAMS](https://open-meteo.com/en/docs/air-quality-api) | Recent modelled dust exposure, fetched on demand | Credit Open-Meteo and CAMS; separate from the typical climate year |
| [Open-Meteo forecast](https://open-meteo.com/en/docs) | Next 7 days of maximum temperature, humidity, UV index, sunlight and ET0 (`planner/site_data.py`) | CC BY 4.0; credit Open-Meteo |
| [EU JRC PVGIS](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en) | GIS solar: PV yield with terrain shading (horizon from a digital elevation model), best tilt, heat loss | Free; credit European Commission JRC |
| [World Bank Open Data](https://data.worldbank.org/indicator/FR.INR.LEND) | Lending interest rate and inflation for the real discount rate in NPV (`planner/finance.py`) | CC BY 4.0; credit World Bank |

Every value in `data/*.csv` has a `source` column. Values marked `estimate` are illustrative, not measured.

### Libraries

| Library | Role | License |
| --- | --- | --- |
| [Streamlit](https://streamlit.io/) | Web app | Apache 2.0 |
| [folium](https://python-visualization.github.io/folium/) + [streamlit-folium](https://github.com/randyzwitch/streamlit-folium) | Map and pin clicks | MIT |
| [Plotly](https://plotly.com/python/) | Charts | MIT |
| [pandas](https://pandas.pydata.org/) + [NumPy](https://numpy.org/) | Tables and maths | BSD-3 |
| [PsychroLib](https://github.com/psychrometrics/psychrolib) | Wet-bulb temperature | MIT |
| [requests](https://requests.readthedocs.io/) | API calls | Apache 2.0 |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | Claude API client | MIT |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Loads `.env` | BSD-3 |
| [pytest](https://pytest.org/) | Tests | MIT |

The Claude API is a paid, closed service and optional: the agent can run on an open-weight model instead (see The AI assistant). If you use Qwen2.5, credit it under Apache 2.0.

## License

MIT, see [LICENSE](LICENSE).
