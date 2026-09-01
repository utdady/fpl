# FPL Research

Projection-first Fantasy Premier League research for 2026/27.

The **projection engine** (`engine/`) estimates points and uncertainty per player.
The **ILP optimizer** picks a legal fifteen, XI, and captain. The **research viewer**
(`web/`) is a read-only UI over frozen records — it does not write back to the model.

**Production defaults** (live re-solves): `minutes_version=v2am_s`, `rates_version=v1`.
**Permanent control** (frozen GW1 pool and historical harness): `v1.0-gw1-baseline`.

## Quick start (engine)

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
python fpl.py --horizon 6 --strategy balanced
```

Strategies: `safe`, `balanced`, `aggressive`.

## Live track (2026/27)

```bash
python fpl.py --refresh
python -m engine.audit --refresh
python -m engine.capture --gw 1          # freeze before deadline
python -m engine.capture --gw 1 --score  # score after results
python -m engine.capture --gw 1 --diagnostics  # sim quantiles, LOO CSV, per-strategy squads
```

## Research viewer (`web/`)

```bash
python scripts/export_ui.py              # records/ + .cache/fpl → web/public/data/
cd web && npm install && npm run dev     # http://localhost:3000
```

Surfaces: **Pool** (frozen predictions), **XI board** (historical elevens + live
strategy re-solve), **Lab** (four-season evaluation), **Audit** (LOO, counterfactuals,
sim diagnostics), **Teams** (track entries, compare, GW edge), **My team** (signed-in
FPL session). See `web/README.md` for deploy notes and strategy refresh cadence.

```bash
.venv\Scripts\python.exe scripts\refresh_strategies.py --force
```

## Historical lab

Vaastav data is cloned automatically on first use into `data/vaastav/`.

```bash
python -m engine.harness_validate --season 2025-26 --gw 1
python -m engine.harness_run --season 2025-26 --gw 1
python -m engine.harness_run --season 2025-26 --gw 1 --score
```

Rolling evaluation and B0–B3 comparison:

```bash
python -m engine.harness_run --season 2025-26 --from-gw 1 --to-gw 38 --skip-existing --skip-validate
python -m engine.harness_run --season 2025-26 --from-gw 1 --to-gw 38 --score --skip-existing
python -m engine.harness_compare --season 2025-26 --from-gw 1 --to-gw 38
```

Decision-error decomposition (V2 investigation; does not change V1):

```bash
python -m engine.harness_decomp --season 2025-26 --from-gw 1 --to-gw 38
python -m engine.harness_decomp --season 2024-25 --from-gw 1 --to-gw 38
```

Observational E008/E009 (does not change V1):

```bash
python -m engine.obs --season 2025-26
```

## Documentation

| Doc | Purpose |
|---|---|
| [`docs/PROJECT.md`](docs/PROJECT.md) | Methods, math, data provenance, experiment map |
| [`docs/LAB_LOG.md`](docs/LAB_LOG.md) | Hypotheses, E-codes, verdicts (append-only) |
| [`ROADMAP.md`](ROADMAP.md) | Version ladder and production vs control |
| [`docs/HARNESS_SPEC.md`](docs/HARNESS_SPEC.md) | As-of-T rules and validation gates |
| [`docs/V2_INVESTIGATION.md`](docs/V2_INVESTIGATION.md) | Nested regret and evaluation protocol |
| [`web/README.md`](web/README.md) | UI export, deploy, live strategy refresh |
