# Formal integrity (Lean 4)

Executable specification for evaluation invariants documented in [`docs/FORMAL.md`](../docs/FORMAL.md).

Python property tests in [`tests/test_e012_integrity.py`](../tests/test_e012_integrity.py) remain the regression harness on real artifacts. Lean makes the definitions and algebraic identities explicit.

## Modules

| File | Matches |
|---|---|
| `FPL/Regret.lean` | `engine.harness_decomp` nested regret columns |
| `FPL/Evaluation.lean` | `engine.harness_decomp.classify_week` |
| `FPL/Leakage.lean` | `engine.obs.LEAKAGE_SPEARMAN` / E008 flag |
| `FPL/Snapshot.lean` | `engine.models.Snapshot` cutoff types |

Not yet formalized: squad/XI legality certificate checker (`engine.optimize`).

## Prerequisites

Install [elan](https://github.com/leanprover/elan) (Lean version manager):

```powershell
# Windows (review script before running)
irm https://raw.githubusercontent.com/leanprover/elan/master/elan-init.ps1 | iex
```

```bash
# macOS / Linux
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
```

## Build

```bash
cd formal
lake update
lake build
```

`lean-toolchain` pins Lean `v4.14.0`.

## Verify Python invariants (no Lean required)

```bash
python -m unittest tests.test_e012_integrity -v
```

## Philosophy

> Python tells us what happened. Statistics tell us whether it is reproducible. Lean tells us whether we accidentally changed the question while measuring it.

Lean is **not** a V2 gate and does not prove calibration, solver optimality, or data provenance.
