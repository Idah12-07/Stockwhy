# StockWhy (working name)

An agent that explains **why a health facility ran out of an essential medicine**, remembers what happened before, and drafts the fix for a pharmacist to approve.

![architecture](architecture.png)

> Open Agent Hackathon 2026. Track 2 (Explain Why), built to meet Track 1 (fragmented data).
> **All data in this repo is synthetic.** Contribution shares are evidence-weighted estimates, not statistics.

## Status (update as you build)

| Part | State |
|---|---|
| Synthetic data generator (seeded, plants a known cause, optional history and noise) | Working |
| 4 agents: Planner, 7 parallel Investigator branches, Critic, Action Drafter; revision loop, retry, escalation, confidence | Working (rule-based) |
| Report, JSON result, agent trace in `logs/` | Working |
| One-page web UI (`python run.py --serve`) | Working: pick a stock-out, see agents, click evidence, approve/edit/reject |
| **Meterless H-MEM** as shared case memory (`meterless/`, `app/tools/meterless_memory.py`) | Working (Node bridge); needs `cd meterless && npm install` |
| **Zetaris** federated queries (`app/tools/zetaris_client.py`) | Client written and tested against a **stand-in server**; **not yet tested on a real Zetaris instance** |
| NVIDIA Nemotron reasoning (`app/tools/nvidia_client.py`) | TODO |
| Bright Data web evidence (`app/tools/brightdata_client.py`) | TODO (reads cached notes offline) |
| Evaluation (`scripts/evaluate.py`) | Working (synthetic data: a sanity check, not real-world accuracy) |

## Run it (no keys needed)

```bash
python run.py --input input_examples/case1.json        # prints a report, writes a trace to logs/
python run.py --serve                                  # one-page UI at http://localhost:8000
```

Python 3.10+ is enough for the baseline. The first run builds a seeded synthetic dataset.

**Try your own case**

```bash
python run.py --scenario-seed 42 --plant-cause demand_surge
python scripts/evaluate.py          # accuracy, precision, recall, F1, calibration (about a minute)
```

## Meterless H-MEM (case memory)

Needs Node.js 18+. One-time: `cd meterless && npm install`. Then:

```bash
python scripts/meterless_smoke_test.py       # proves remember, recall, audit and feedback work
python run.py --serve                        # memory is on automatically when available
python run.py --input input_examples/case1.json --memory meterless
```

Each finished case is stored in H-MEM. The next time the same facility has a stock-out, the agents recall the earlier case; if the cause repeats, the report flags a **repeat issue** and changes the recommended process fix. Approving or rejecting a draft in the UI sends feedback to H-MEM. The memory engine is Meterless's open-source reference implementation, vendored unchanged in `meterless/hmem/` (Apache-2.0).

## Zetaris (federated data)

Settings go in `.env` (see `.env.example`). Steps:

1. `python scripts/export_postgres_sql.py` writes `postgres_load.sql` and `zetaris_register.sql` next to the data.
2. Load the synthetic data into a Postgres database and register it in Zetaris (or load the CSVs by whatever route the organisers provide).
3. `python scripts/zetaris_smoke_test.py` checks the connection step by step and prints the raw responses.
4. `python run.py --mode live --input input_examples/case1.json` runs the same investigation through Zetaris.

`python scripts/test_zetaris_path.py` proves our client logic against a stand-in server (not Zetaris itself).

## Docker

```bash
docker build -t stockwhy .
docker run stockwhy                                              # one report
docker run -p 8000:8000 stockwhy python run.py --serve --host 0.0.0.0   # the UI at http://localhost:8000
```

## Agents

| Agent | Role | Input | Output | Collaborates with |
|---|---|---|---|---|
| 1. Planner | Checks a stock-out exists, recalls earlier cases, lists hypotheses | Facility, medicine, month | Plan | Delegates to Agent 2 |
| 2. Investigators | One parallel branch per hypothesis, retry on failure | One hypothesis | Evidence with source rows | Reports to Agent 3 |
| 3. Critic and Ranker | Ranks causes, scores confidence, re-checks close calls once, escalates low confidence | All evidence | Ranked causes | Revision loop with Agent 2; reads and writes case memory |
| 4. Action Drafter | Finds nearby surplus stock, drafts a transfer and requisition | Ranked causes | Draft for human approval | Pharmacist |

## Examples

`input_examples/` holds 5 inputs; `output_examples/` the 5 matching outputs, produced by `scripts/make_examples.py`, never by hand.

## Why nothing is hardcoded

Conclusions are computed from the data at run time. The planted cause is returned only to scripts that evaluate the agent; `app/` never reads `scripts/_truth/`.

## Limitations

- Synthetic data: accuracy on real facility data is unproven.
- Seven hypotheses may miss real causes; the agent then reports low confidence and escalates.
- Reasoning is rule-based until NVIDIA Nemotron is wired in.
- Nothing is sent automatically; every action is a draft for a human.

## Sponsor technologies (fill in as you integrate)

| Sponsor | Where it fits | Where in the code |
|---|---|---|
| Zetaris | Federated queries over stock, orders, payments | `app/tools/zetaris_client.py` |
| Meterless | H-MEM shared case memory with audit trail and feedback | `meterless/`, `app/tools/meterless_memory.py` |
| NVIDIA | Critic reasoning, document extraction | `app/tools/nvidia_client.py` |
| Bright Data | Public web evidence | `app/tools/brightdata_client.py` |
| Cursor | Development environment | `.cursor/rules/` and the section below |

## How we used Cursor

_Fill in: what you built with it, example prompts, screenshots._

## Team and contributing

Short branches, small pull requests into `main`, keep `main` runnable, run `python scripts/evaluate.py` before merging, never commit `.env`.
