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
python fpl.py suggest --squad myteam.json
python fpl.py suggest --squad myteam.json --allow-hit --json
```

Strategies: `safe`, `balanced`, `aggressive`. `suggest` is a **next-GW FT-spending
optimizer** (highest projected XI+C given available free transfers) — not a selective
“should you transfer?” advisor, and not V5/V7. Default is free transfers only; pass
`--allow-hit` for the aggressive FT+1 / −4 option. My team Transfers uses the same
command locally (`allow_hit` off unless you opt in).

Product confidence replay (not an E-card):

```bash
python scripts/product_transfer_replay.py --season 2022-23 --to-gw 8
python scripts/product_transfer_replay.py --all-seasons --to-gw 38
python scripts/product_transfer_replay.py --season 2022-23 --both-conditions --to-gw 8
```

## Live track (2026/27)

Per-player μ (pre-deadline) and actuals (post `data_checked`) live in
`records/gwNN_v1.0.csv`. Aggregates append to `records/scores.csv`.

**Automated (GitHub Actions):** `.github/workflows/live-capture.yml` runs every
6h UTC — freeze next GW inside a 48h pre-deadline window if missing; score any
unscored freeze once FPL marks `data_checked`; export UI and commit artifacts.
Manual: Actions → live-capture → Run workflow. Never invents post-deadline freezes.

```bash
python scripts/live_capture_ops.py              # freeze + score as needed
python scripts/live_capture_ops.py --dry-run
python -m engine.capture --gw 5 --refresh       # manual freeze
python -m engine.capture --gw 5 --score         # manual score after results
python -m engine.capture --gw 5 --diagnostics
python scripts/export_ui.py
```

```bash
python fpl.py --refresh
python -m engine.audit --refresh
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

Formal integrity (optional; not a V2 gate):

```bash
python -m unittest tests.test_e012_integrity tests.test_certificate -v
cd formal && lake build                            # Lean 4 (requires elan)
python -m engine.certificate path/to/cert.json     # verify emitted certificate
```

## Tests

Ordinary runs stay fast. Full-season historical recomputes are opt-in.

```bash
# Fast: policy / wiring / formal (skips recommend_historical recomputes)
python -m unittest tests.test_e040_tc_policy tests.test_e041_bb_policy `
  tests.test_e046_fh_wiring tests.test_e050_wc_policy tests.test_e050_wc_wiring `
  tests.test_e051_chip_conflict tests.test_e012_integrity tests.test_certificate -v

# Slow: full as-of-T parity for one season per chip (minutes each)
$env:FPL_RUN_SLOW=1
python -m unittest tests.test_e040_tc_policy tests.test_e041_bb_policy `
  tests.test_e046_fh_wiring tests.test_e050_wc_wiring -v
```

See [`formal/README.md`](formal/README.md) and [`docs/FORMAL.md`](docs/FORMAL.md).

## Documentation

| Doc | Purpose |
|---|---|
| [`docs/PROJECT.md`](docs/PROJECT.md) | Methods, math, data provenance, experiment map |
| [`docs/LAB_LOG.md`](docs/LAB_LOG.md) | Hypotheses, E-codes, verdicts (append-only) |
| [`ROADMAP.md`](ROADMAP.md) | Version ladder and production vs control |
| [`docs/HARNESS_SPEC.md`](docs/HARNESS_SPEC.md) | As-of-T rules and validation gates |
| [`docs/FORMAL.md`](docs/FORMAL.md) | Evaluation invariants; Lean spec in `formal/` |
| [`formal/README.md`](formal/README.md) | Build Lean 4 formal core (`lake build`) |
| [`docs/V2_INVESTIGATION.md`](docs/V2_INVESTIGATION.md) | Nested regret and evaluation protocol |
| [`web/README.md`](web/README.md) | UI export, deploy, live strategy refresh |
