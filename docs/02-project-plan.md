# Project plan: Farming the Desert Sun

Sep 25, 2026 · @Blay

## 1. Goal and deliverables

**By Saturday's judging, demo a working web app: drop a pin in Qatar and get back the best crop, setup, solar size and payback, with every number traceable to open data.**

We submit four things:

1. **Working prototype:** a web app that runs live, not slides pretending to be an app.
2. **Public GitHub repo:** MIT license, clean code, README, credits for all data and libraries.
3. **Pitch deck:** about 6 slides, problem to solution to demo to impact.
4. **Demo video (backup):** a 2-minute screen recording in case the live demo fails.

## 2. Scope

**Build the must-haves first and demo them end to end before touching anything else.** Stretch items only start once the full pipeline works.

| Priority | Feature | Why |
| --- | --- | --- |
| Must-have | Pin on map, fetch NASA POWER data | Everything depends on it |
| Must-have | Crop check: which crops fit which months | Challenge 1 feature: site suitability |
| Must-have | Cooling simulation for 4 setups (8,760 hours) | Our unique insight |
| Must-have | Solar sizing and payback for each setup | Challenge 1 feature: investment planning |
| Must-have | Results screen with recommendation and comparison table | What judges see |
| Must-have | LLM explanation with number checker | Responsible AI criterion |
| Stretch | Chat follow-ups ("what if I double the budget?") | Shows the agent re-running tools |
| Stretch | Dust light-loss from Open-Meteo | Extra ML/data depth |
| Stretch | 2040 climate view | Climate-change story |
| Roadmap only | Satellite imagery, SMS delivery, soil sensors | Mention in pitch, do not build |

Keep the demo to about 8 crops and Qatar sites, but never hard-code Qatar: any pin on Earth should run.

## 3. Modules

**Six modules, each a plain Python function with a fixed input and output, so people can build them in parallel.** Agree on these interfaces in the first hour and do not change them.

| # | Module | Input | Output |
| --- | --- | --- | --- |
| 1 | `climate.py` | lat, lon | Hourly table: temp, humidity, solar radiation, wind (typical year) |
| 2 | `crops.py` | climate table, crop list | For each crop, which months it can grow in open field |
| 3 | `cooling.py` | climate table, crop heat limit, setup | Inside temperature per hour, coverage % |
| 4 | `solar.py` | climate table, cooling energy needed | Panel size (kW), yearly solar output |
| 5 | `economics.py` | setup, crop, farm size, prices | Build cost, running cost, profit per year, payback |
| 6 | `agent.py` | user goal + all tool outputs | Ranked plan + checked plain-language explanation |

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

**Three people, three layers.** Full step-by-step instructions are in the Team tasks tab.

| Person | Owns |
| --- | --- |
| Me (repo owner) | Repo, data pipeline, cooling physics, optimizer, main app |
| Salih | AI agent, number checker, English/Arabic chat |
| Mustafa | Data tables, crop check, solar sizing, economics, README credits |

## 5. Timeline

**Friday builds the engine; Saturday polishes, freezes code and rehearses.** Times assume judging on Saturday afternoon; shift everything once we confirm the real deadline from the Participant Handbook.

| When | Milestone | Checkpoint |
| --- | --- | --- |
| Fri 09:00–10:00 | Kickoff: agree module interfaces, create repo, add MIT license | Repo public, everyone can push |
| Fri 10:00–13:00 | Each role builds its module on fixed test data | Each module runs alone in the terminal |
| Fri 13:00–14:00 | Lunch + mentor check-in on Slack | Feedback noted |
| Fri 14:00–17:00 | Connect modules: pin to data to cooling to payback | **Full pipeline prints a plan in the terminal** |
| Fri 17:00–21:00 | Streamlit app with map and results screen; agent + number checker | Pin to results screen works in the browser |
| Fri 21:00–23:00 | Stretch features only if the pipeline is solid; draft slides | Deck skeleton done |
| Sat 08:00–10:00 | Bug fixes, test 5 different pins, README | App works on every test pin |
| Sat 10:00 | **Code freeze.** No new features after this | Final commit tagged |
| Sat 10:00–11:00 | Record backup demo video | Video saved |
| Sat 11:00–13:00 | Finish deck, rehearse the pitch 3 times with a timer | Pitch fits the time limit |
| Sat afternoon | Submit and present | Submitted |

The one rule that matters: if the full pipeline is not working by Friday 17:00, drop all stretch items and make the must-haves solid.

## 6. Repo structure and stack

**One public repo, one folder per module, all assumptions in editable CSV files.** Anyone in another country can swap in local prices and crops without touching code.

```
desert-farm-planner/
├── app.py              # Streamlit app: map, inputs, results
├── planner/
│   ├── climate.py      # NASA POWER fetch + typical year
│   ├── crops.py        # crop-by-month check
│   ├── cooling.py      # wet-bulb + 8,760-hour simulation
│   ├── solar.py        # panel sizing (pvlib)
│   ├── economics.py    # cost, profit, payback
│   └── agent.py        # LLM agent + number checker
├── data/
│   ├── crops.csv       # heat limits (from FAO EcoCrop)
│   ├── setups.csv      # build and running costs per setup
│   └── prices.csv      # crop prices (FAOSTAT)
├── tests/              # one test per module
├── README.md           # problem, how to run, credits
└── LICENSE             # MIT
```

| Layer | Tool |
| --- | --- |
| Language | Python 3.11 |
| App and map | Streamlit, Folium (Leaflet) |
| Physics | PsychroLib, pvlib, NumPy, pandas |
| Data | NASA POWER API, Open-Meteo API, FAO EcoCrop, FAOSTAT |
| AI agent | Claude API with tool use, temperature 0 |
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
| NASA POWER is slow or down during the demo | Cache the data for both demo pins as local files on Friday |
| Venue Wi-Fi fails | Run the app locally; backup video as last resort |
| LLM API fails or is slow | App shows the full plan without the explanation; physics still works |
| Cost and price numbers are rough | Label them "illustrative, editable in CSV"; judges value honesty |
| Crop heat limits are hard to find | Start with 8 well-known crops typed in by hand from EcoCrop |
| Modules don't fit together | Interfaces fixed in hour one; test with fake data early |
| Running out of time | Drop stretch features at Friday 17:00, never the must-haves |

## 9. Submission checklist

**Tick these off before the code freeze; open-source rules are a hard requirement.**

- [ ] Repo is public with an MIT license from the first commit
- [ ] All code written during the hackathon; every library and dataset credited in the README
- [ ] README covers the problem, how to run, architecture diagram, data sources and limits
- [ ] Demo pins tested and data cached locally
- [ ] Backup demo video recorded
- [ ] Pitch deck final and rehearsed with a timer
- [ ] Submitted in the format the Participant Handbook asks for

### Open questions

- [ ] What is the exact submission deadline and format? Check the Participant Handbook QR code.
- [ ] What does the academic integrity policy say about using AI assistants?
- [ ] How long is the pitch? Adjust the demo script to fit.
- [ ] How many people are on the team? Adjust the roles table.
