# Optional update — implementation and validation

Branch: `jawad/optional-update`. Based on `salih/openrouter`, which already contains
`jawad/redesign`. No pull request is created and `main` is unchanged.

## Implemented

1. **Sunlight:** NASA hourly PAR, UVA, UVB, longwave, clear-sky shortwave and clear-sky
   PAR. The live API returned MJ/hr; all fluxes are converted to hourly mean W/m².
   UV is UVA + UVB. NIR is the nonnegative remainder of shortwave − PAR − UV, an
   approximate band split, not a measured spectral curve. Heat share is undefined
   at night. Cache version and requested year range prevent old climate files from
   silently masquerading as spectral data. Source metadata records years and errors.
2. **Humidity:** inside relative humidity and daylight VPD stress hours. Pad moisture
   uses an approximate constant-enthalpy calculation at sea-level pressure. This is
   not a full greenhouse mass/energy balance or disease-risk model.
3. **Light:** DLI from PAR, with transmission per setup. At least 90% of days in
   temperature-qualified growing months must meet the crop's minimum DLI. Missing
   light data excludes a recommendation rather than assuming adequate light.
4. **Seven setups:** the original four plus NIR-screen wet pad, fixed agrivoltaics
   and moving agrivoltaic louvers. New equipment, transmission, DLI and VPD values
   are explicitly **estimates**. Agrivoltaic structure cost excludes panels; panel
   capacity is charged separately. PV orientation and tracking are simplified.
5. **Controller:** shared rule-based screen decisions, 10% movement steps, bounded
   closure, heat hysteresis, light protection and night opening. Thresholds live in
   `data/settings.csv`; no learned model or real hardware is involved.
6. **Operate:** six-page app with a one-day, 144-step simulator, Play/Pause/Reset,
   fixed/smart comparison, decision reasons and CSV export. Weather is held constant
   within each source hour. The planner advances the controller hourly; the demo
   advances it every ten minutes, so transitional positions can differ. No claim
   that the smart setup always outperforms fixed shade is made.
7. **Dust:** optional 7/14/30-day cleaning scenarios account for assumed soiling,
   light/yield loss, PV loss, cleaning expense and water. Open field has no structure
   cleaning charge. NASA's all-sky light already includes atmospheric attenuation;
   clouds are not falsely labelled dust or deducted twice. A separate on-demand
   panel reads the last 30 days of CAMS dust via Open-Meteo, reports missing hours
   and never extrapolates it into a multi-year dust climatology.
8. **Area scan:** draw a rectangle and compare a 2×2 to 5×5 grid. Results and errors
   are per point and exportable. Nearby points may share a satellite grid cell;
   this is not parcel-level measurement. Dateline-crossing rectangles are rejected.
9. **Integration:** English/Arabic labels, setup colours, diagnostics, source records,
   shareable cleaning scenarios, regression tests and GitHub Actions. New option
   diagnostics travel through the existing `assumptions` field already forwarded by
   the assistant; the existing number checker recursively reads them.

## Existing gap corrected

Solar generation and cooling are now balanced **hour by hour**. Uncovered demand
incurs the configured grid tariff. Surplus earns the configured sell tariff, zero
by default. This assumes a grid-connected site, with no battery or free nighttime
storage. Grid access and any export agreement still need confirmation by the user.
No guaranteed investment return is implied by the estimated costs and crop yields.

## Validation

- Offline engine, agent, checker, climate, controller, simulator and bilingual page
  tests: **87 passed**, using `python -m pytest -q` on Python 3.11.
- Real NASA validation and optional cache warm-up:
  `python scripts/validate_demo.py --five-sites`.
- Results are recorded in [validation/live-data.json](validation/live-data.json).
  All five Qatar sites returned 56 crop/setup options using 2021–2025 NASA data.
  Cached hourly weather remains local in the ignored `data/cache/` directory.
- Public NASA spectral parameter availability and units were checked live. The
  recent CAMS/Open-Meteo endpoint was also checked live, without credentials.
- Browser checks cover simulator playback, Arabic switching and a narrow viewport.

## Reserved for the teammate

No new changes to `planner/agent.py`, `planner/chat_ui.py`, `.env.example`, model
identifiers, provider selection, API keys or Streamlit Secrets. These retain the
existing OpenRouter branch content. Live LLM verification remains with the teammate.

## Still requires real-world or team work

- Vendor quotes and local crop/price sources; agronomist validation of all assumed
  heat, humidity, light, yield and water parameters.
- A native speaker's final Arabic review and live English/Arabic chat transcripts.
- Confirm the demo deployment branch; prepare the team pitch, record the backup
  video, rehearse and submit according to the participant handbook. This branch
  does not publish the site or submit anything.
- Existing optional UI gaps: in-app assumption editing, direct PDF export and
  place-name search. Assumptions remain editable CSVs; plans export as JSON.
- Full greenhouse energy balance, cold protection, labour/land/financing,
  discounting, equipment replacement and extreme-weather modelling are not added.
- Hardware, cameras, ESP32, reinforcement learning and future-climate prediction
  remain explicitly outside the hackathon implementation scope.

## Technical sources

- [NASA POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/)
- [NASA POWER energy flux methodology](https://power.larc.nasa.gov/docs/methodology/energy-fluxes/)
- [CAMS/Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)

These references support weather inputs and access methods; they are not cited as
evidence for the estimated commercial equipment, crop or financial assumptions.
