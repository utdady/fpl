# FPL V1

Projection-first Fantasy Premier League squad picker for 2026/27.

The projection engine is the brain. The ILP optimizer is the decision layer.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
python fpl.py --horizon 6 --strategy balanced
```

Strategies: safe, balanced, aggressive.

## Live track (2026/27)

```bash
python fpl.py --refresh
python -m engine.audit --refresh
python -m engine.capture --gw 1          # freeze before deadline
python -m engine.capture --gw 1 --score  # score after results
```

## Historical lab (2024/25 + 2025/26)

Vaastav data is cloned automatically on first use into data/vaastav/.

```bash
python -m engine.harness_validate --season 2025-26 --gw 1
python -m engine.harness_run --season 2025-26 --gw 1
python -m engine.harness_run --season 2025-26 --gw 1 --score
```

See docs/PROJECT.md for methods, math, data provenance, and the experiment map.
See docs/HARNESS_SPEC.md for as-of-T rules and validation gates.
See docs/FORMAL.md for evaluation-integrity invariants (post-GW1, not a V2 gate).
See ROADMAP.md for the full version ladder.

Rolling evaluation and B0-B3 comparison:

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

See docs/V2_INVESTIGATION.md.

Experiment log: docs/LAB_LOG.md
Project methods (encyclopedia): docs/PROJECT.md

Observational E008/E009 (does not change V1):

    python -m engine.obs --season 2025-26
