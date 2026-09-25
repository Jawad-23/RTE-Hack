# Project docs

Planning documents for our Reboot the Earth Doha 2026 project (Challenge 1). Read them in this order:

| File | What it covers |
| --- | --- |
| [01-problem-and-solution.md](01-problem-and-solution.md) | The problem, how we solve it, the AI agent and hallucination guardrails, APIs, what we add next, the Plan → Build → Operate roadmap, solution map. |
| [02-project-plan.md](02-project-plan.md) | Goal, scope with the status of every feature, modules and formulas, timeline, repo structure, demo script, risks, submission checklist. |
| [03-team-tasks.md](03-team-tasks.md) | Who does what, architecture, shared contracts, team rules, branches, each person's done and next tasks, the stage 2 plan. |
| [04-hackathon-brief.md](04-hackathon-brief.md) | The official challenge, rules, code of conduct, IP policy and judging criteria (unchanged). |
| [assets/](assets/) | Original challenge slides, brainstorm notes and the opening ceremony deck. |

**These markdown files are kept in sync with the code and are the source of truth.** When code changes a contract, a status or a number, update the docs in the same pull request.

- The [PDF version](01-problem-and-solution.pdf) of the problem-and-solution doc is the Sep 24 snapshot with the charts and mockup. It does not include later updates.
- The shared Claude Doc these files were exported from is now behind them. Copy changes back to it, or stop using it.

## What changed on Sep 25

- Stage 1 is built: the whole app runs end to end on the stacked branches (see [Team tasks, section 4](03-team-tasks.md#branches-right-now)).
- The agent sends no temperature setting (the model rejects it); the number checker keeps answers grounded.
- pvlib is not used; solar output comes straight from NASA POWER sunlight.
- The agent can run on an open-source model through any OpenAI-compatible server, not only Claude.
- The project plan now lists every known gap: APIs never run live, estimated numbers and simplifications ([section 10](02-project-plan.md#10-known-gaps-what-is-not-real-yet)).
- The planner uses the 5 most recent full years of NASA data, not 20+.
- All values in `data/*.csv` are labelled `estimate` until someone finds a source.
- Stage 2 (smarter shading and dust) is planned, with an owner for every piece.
- Cameras, ESP32 and all other hardware are roadmap only.
