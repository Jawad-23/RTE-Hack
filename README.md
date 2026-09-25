# RTE Hack: Farming the Desert Sun

Our project for the **Reboot the Earth** hackathon (Doha 2026, Challenge 1). Drop a pin anywhere hot and dry and the app tells you what to grow, what setup to build (open field, shade net, wet-pad greenhouse or solar chiller greenhouse), how much solar to install and when it pays off. Every number comes from open data or an editable CSV.

## Run it

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then paste your own ANTHROPIC_API_KEY (never commit .env)
streamlit run app.py
```

Print a plan in the terminal without the app:

```bash
python -m planner.optimizer 25.29 51.53 --area 500 --budget 250000 --priority profit
```

Run the tests: `python -m pytest`

The first run for a new pin fetches 5 years of hourly data from NASA POWER (can take a minute) and caches it in `data/cache/`. If the map can't load, use **Or type coordinates** under it.

## Layout

| Path | What | Owner |
| --- | --- | --- |
| `app.py` | Streamlit app: map, inputs, results dashboard | Repo owner |
| `planner/schemas.py` | Shared column names, setups, statuses, units | Repo owner |
| `planner/climate.py` | NASA POWER fetch → 8,760-hour typical year, cached | Repo owner |
| `planner/cooling.py` | Wet-bulb physics and inside temperature per setup | Repo owner |
| `planner/optimizer.py` | Runs every crop × setup, filters, ranks: `plan()` | Repo owner |
| `planner/crops.py`, `solar.py`, `economics.py`, `data/*.csv` | Crop check, solar sizing, economics, data tables | Mustafa (stubs for now) |
| `planner/agent.py`, `checker.py`, `chat_ui.py`, `i18n/`, `styles/rtl.css` | AI agent, number checker, English/Arabic chat | Salih (stubs for now) |
| `tests/` | One test file per module | everyone |
| `docs/` | Problem, plan, team tasks, hackathon brief ([start here](docs/README.md)) | |
| `ui-demo/` | Croptions UI prototype and design system (open `Croptions.dc.html`) | |

Stubs return fake but correctly shaped data, so the whole app runs end to end while each module is being built. The values in `data/*.csv` are placeholders marked `PLACEHOLDER` until real sources are filled in.

## How we work

Branch per person and module (`jawad/core`, `mustafa/economics`, …), only edit files you own, and open a pull request into `main`. Full rules: [docs/03-team-tasks.md](docs/03-team-tasks.md#4-rules-for-everyone).

## Credits

Data: [NASA POWER](https://power.larc.nasa.gov/) (climate), [FAO EcoCrop](https://gaez.fao.org/pages/ecocrop) (crop limits), [FAOSTAT](https://www.fao.org/faostat/) (prices). Libraries: Streamlit, folium, streamlit-folium, Plotly, pandas, NumPy, PsychroLib, requests, the Anthropic Python SDK. Full credits section to come (Mustafa).

## License

MIT, see [LICENSE](LICENSE).
