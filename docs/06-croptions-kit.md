# Croptions Kit (simulated)

**Croptions plans the farm. The Croptions Kit protects it.** The kit is the Operate stage: sensor pods that watch the crop and advise the smart screen. There is no hardware yet. A hidden simulator page plays the kit and sends simulated readings; the readings CSV marks each one `simulated`.

| Stage | Question | Where | Real or simulated |
| --- | --- | --- | --- |
| Plan | What to grow, with which setup; does it pay? | Plan → Results | Real: NASA POWER, FAOSTAT, our physics |
| Build | What does it cost, with the kit? | Results → "Croptions Kit" card | Real calculation; kit prices are fixed placeholders |
| Operate | How is the crop doing right now? | Croptions Kit page (`/kit`) | Simulated readings from `/kit-simulator` |

## Demo in one minute

1. Analyse a site (for example **Try Al Khor**). Results shows the assistant's summary, the **Croptions Kit** card, investment scenarios and site intelligence.
2. Open **✦ Croptions Kit** in the top bar (or **☰ Menu**). It shows a 4-digit **Kit ID**.
3. In another tab or on a phone, open the hidden simulator: `/kit-simulator?farm=<Kit ID>` (not linked in the app; see the README section "Try the Croptions Kit").
4. Select **Heat stress**. Within about two seconds the Kit page shows the reading, the crop water stress (CWSI), the alerts and the kit's advice ("move screen to 80%").
5. Pick a control mode: **Auto** (moves the screen), **Approve once** (waits for your click) or **Manual** (you set it).
6. Press **Stream the day** to send one reading every two seconds from 05:00 to 20:00.
7. **Download readings CSV** feeds the 3D video, so the animation shows exactly what the software decided. Every row says `source = simulated`.

A phone cannot open `localhost`: run with the Network URL Streamlit prints, or use the deployed site.

## How a reading is made

1. The kit page takes the site's NASA typical year, today's date and the recommended setup, and runs `cooling.hourly_profile` for that day. This gives the hourly inside air temperature, humidity and growing light.
2. A scenario from `data/kit_scenarios.csv` shifts that hour: hotter, drier, brighter, or a humid night. It also sets how stressed the leaf is.
3. The leaf temperature sits between the transpiring baseline and the non-transpiring limit (below). Small sensor noise is added (`kit_noise_*` in `data/settings.csv`).

A reading is a plain dict, the same shape a real pod could post later:

```json
{"farm_code": "4821", "seq": 7, "sent_at": "2026-09-25T13:10:02+00:00", "sim_day": 268, "sim_hour": 14,
 "scenario": "heat_stress", "leaf_c": 47.3, "air_c": 44.2, "rh_pct": 38.0, "par_w_m2": 276.1, "source": "simulated"}
```

## What the dashboard calculates (`planner/kit.py`)

| Metric | How | Alert |
| --- | --- | --- |
| VPD (kPa) | Tetens saturation pressure × (1 − RH) | Above the crop's `vpd_max_kpa` |
| Dew point, leaf gap (°C) | Inverse Tetens; leaf minus dew point | Gap below `kit_dew_gap_alert_c` (mould risk) |
| CWSI (0–1) | (leaf − air − lower baseline) / (upper limit − lower baseline). The lower baseline is `a + b × VPD` (the form from Idso et al. 1981). Daylight only | At or above `kit_cwsi_alert` |
| Leaf too hot | Leaf above the crop's `t_max_c` | Yes |
| Light so far today | Latest PAR per simulated hour × 3,600 s × `par_umol_j` | Compared with `dli_min_mol_m2_day` |
| Screen advice | The same `controller.decide` rule the planner uses, run until it settles | — |
| Thermal image | 32 × 24 grid, crop rows plus stress hot spots (labelled illustrative in the app). The mean leaf temperature equals the reading; the pattern is illustrative | — |

Alerts are logged when they start, not on every reading. The CWSI coefficients, alert limits, noise and scenarios are all **estimates** in CSV files. They are not crop-calibrated.

## Cost

`kit.costs()` adds `ceil(area / kit_pod_area_m2)` pods at `kit_pod_price_qar` (2,000 QAR) plus `kit_service_qar_year` (300 QAR a pod). It reports build cost, yearly profit and payback with the kit next to the plan without it. These are fixed placeholder prices, not quotes. **No yield gain from the kit is assumed.** The only calculated benefit is `planner/operate.simulate_day`, which compares fixed shade with the smart screen for one day; it is the **Fixed shade vs the kit's smart screen** section at the bottom of the Kit page.

Every simulated reading is tagged **Demo reading · simulated** on the Kit page, and the Results card calls it the latest demo reading. The thermal image is described as illustrative.

## How the simulator reaches the dashboard

The simulator and the Kit page are two Streamlit sessions. They share one in-memory `KitStore` (`st.cache_resource` in `ui/kit_ui.py`): farm code → context + readings. The dashboard polls it every two seconds (`st.fragment(run_every=2)`).

Limits:

- Readings are lost when the app restarts.
- Codes expire after 24 hours.
- It works while the whole app runs as one server process, which is how Streamlit Community Cloud runs it.

This is still software only: no microcontroller, sensor, MQTT or device code.

## Not included (roadmap slide)

- Real pods (thermal camera, ESP32).
- PRI and chlorophyll fluorescence: we cannot simulate them honestly.
- A learned controller.
- Any yield-saving percentage without a source.

## Code freeze

The code freeze is the time after which nobody adds features: only bug fixes, rehearsal and recording the backup video. It keeps the live demo stable. Set it a few hours before submission (the plan pencilled in Saturday 10:00).
