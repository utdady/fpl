# Formal integrity (Lean 4)

Executable specification for evaluation invariants and squad certificates.
Philosophy and inventory: [`docs/FORMAL.md`](../docs/FORMAL.md).

Python property tests remain the regression harness on real artifacts:

- [`tests/test_e012_integrity.py`](../tests/test_e012_integrity.py)
- [`tests/test_certificate.py`](../tests/test_certificate.py)

## Locked shape

```text
Regret        → real telescoping theorem
Evaluation    → classifyWeek + typed EvalFlag
Leakage       → dependency contract (Spearman opaque)
Snapshot      → type-level cutoff (not provenance)
Squad/Lineup  → legality predicates
Certificate   → verify returned decision (not CBC)
```

Python emits `SquadCertificate` JSON (`engine/certificate.py`); Lean
`verifyCertificate` checks legality under `rulesVersion` / declared rules.
**Do not expand conceptually** beyond this — sit quietly in the repo.

## Modules

| File | Role |
|---|---|
| `FPL/Regret.lean` | Nested regret identity |
| `FPL/Evaluation.lean` | `classifyWeek` + `EvalFlag` |
| `FPL/Leakage.lean` | Leakage dependency contract |
| `FPL/Snapshot.lean` | Type-level snapshot cutoff |
| `FPL/Squad.lean` | Legal 15 predicates |
| `FPL/Lineup.lean` | Legal XI predicates |
| `FPL/Certificate.lean` | Certificate checker |

## Build

```bash
cd formal
lake update
lake build
```

`lean-toolchain` pins Lean `v4.14.0`. CI: `.github/workflows/formal.yml`.

## Verify without Lean

```bash
python -m unittest tests.test_e012_integrity tests.test_certificate -v
python -m engine.certificate path/to/cert.json
```
