# Formal integrity

> **Lean can prove that our experiment means what we say it means. It cannot prove that our data is truthful.**
>
> Python tells us what happened. Statistics tell us whether it is reproducible. Lean tells us whether we accidentally changed the question while measuring it.

This is **not** a V2 gate. See `LAB_LOG.md`, `HARNESS_SPEC.md`, `V2_INVESTIGATION.md`.

---

## Locked diagnosis (2026-09-09)

```text
Lean today
├── Regret        → 1 real theorem (telescoping identity)
├── Evaluation    → faithful executable spec + typed EvalFlag
├── Leakage       → dependency contract (Spearman opaque; Python authority)
└── Snapshot      → type-level cutoff contract (not provenance)

Certificate track (mature enough to sit quietly)
├── Squad / Lineup predicates
├── Certificate.lean (verify returned decision)
└── engine/certificate.py (JSON emit + Python mirror verify)
```

**Architecture:** Python emits; Lean verifies the answer — never re-solves CBC.

```text
CBC / PuLP
    ↓
solve_squad → SquadCertificate (JSON)
    ↓
verify_certificate (Python mirror)  and/or  Certificate.lean
    ↓
"this returned decision is legal under declared rules_version"
```

Do **not** expand the formal track conceptually after Certificate. No MC, no CBC
optimality, no Spearman body, no promote bars in Lean.

---

## Division of labour

| Owner | Owns |
|---|---|
| **Python** | data reconstruction, μ, minutes, fixtures, MC, calibration, backtests, optimizer execution, Spearman, provenance |
| **Lean** | dependency boundaries, algebraic identities, legal-state predicates, certificate checking, evaluation-status definitions |

```text
             PYTHON
        empirical system
              │
              │ emits typed artifact
              ▼
             LEAN
      verifies invariant
```

---

## Three dependency graphs

| Artifact | May depend on | Must not depend on |
|---|---|---|
| `predict(Snapshot T)` | fields permitted at cutoff T | actuals at T or later; post-deadline columns |
| `LeakFlag` | B0 `xP` and actuals | V1 / V2 / challenger scores |
| `evaluation_status` | fixtures, integrity, structure, optionally `LeakFlag` | model error, MAE, XI+Cap, regret |

---

## Regret identity names its oracle

```text
R_total = R_squad + R_XI + R_cap = P(oracle) - P(V1 realized)
```

Relative to the god-mode nested oracle, **not** the B0 gap. See `B0Gap` in Lean.

---

## Type-level cutoff vs provenance

`Snapshot gw` / `Predictor gw` are a **type-level cutoff**: the predictor cannot
take `Actuals` as a parameter. That is not provenance. Contaminated fields can
still inhabit the type. Provenance stays in `HARNESS_SPEC.md` / `harness_validate`.

---

## What we will not formalize

- CBC / PuLP optimality (verify the certificate, not the solver)
- Calibration, MAE, “V2 is better,” “Haaland is optimal”
- Minutes / rates / packaging / Monte Carlo
- Full Spearman implementation (stays opaque; Python authority)

---

## Implementation inventory

Living record of what `formal/` contains. Update when a module lands or scope
changes. Do **not** log CI plumbing here.

| Module | Role | Python source | Lean artifact | Regression |
|---|---|---|---|---|
| `Regret.lean` | Real theorem: telescoping regret identity; `B0Gap` separate | `harness_decomp.evaluate_gw` | `regret_identity` / `regret_identity_int` | `TestRegretIdentity` |
| `Evaluation.lean` | Executable spec of `classify_week`; typed `EvalFlag` | `classify_week` | `classifyWeek`; `EvalFlag` | `TestEvaluationStatusIndependence` |
| `Leakage.lean` | **Dependency contract** only; Spearman opaque | `obs.LEAKAGE_SPEARMAN` | `LeakInput`; `leakFlag` | `TestLeakFlagIndependence` |
| `Snapshot.lean` | Type-level cutoff contract (not provenance) | `models.Snapshot` | `Snapshot gw`; `Predictor gw` | `harness_validate` |
| `Squad.lean` | Legal 15 predicates | `optimize.solve_squad`; `default_squad` | `isLegalSquad` | `test_certificate` |
| `Lineup.lean` | Legal XI formation windows | `optimize.solve_xi` | `isLegalXI` | `test_certificate` |
| `Certificate.lean` | Verify returned decision + `rulesVersion` / `snapshotId` | `engine.certificate` | `verifyCertificate` | `test_certificate` |

**Evaluation note:** `joinFloor(nSnapshot) = max(50, ⌊0.15 · nSnapshot⌋)`.

**Certificate note:** `claimedObjectiveMilli` is recorded (utility×1000). Lean checks
structural legality and cost consistency; it does not re-derive float CBC utilities.

### Queued / stopped

| Item | Status |
|---|---|
| Further conceptual Lean modules | **stop** — track is mature enough to sit quietly |
| Chip semantics in Lean | not started; premature |
| Objective float reconstruction in Lean | optional later; not required |

**Authority:** `tests/test_e012_integrity.py` + `tests/test_certificate.py` on artifacts.
Lean definitions + `lake build` for the formal layer. Not a V2 gate.

---

## Python certificate API

```bash
# After solve_squad — emit JSON
python -c "from engine.certificate import build_certificate, write_certificate, verify_certificate"

# Verify a file
python -m engine.certificate path/to/cert.json

# Property tests
python -m unittest tests.test_certificate tests.test_e012_integrity -v

# Lean
cd formal && lake build
```

`rules_version` default: `fpl-default-v1` (must match Lean `rulesVersionDefault`).

---

**Status:** E012 Python PASS; E012-lean core landed; E012-cert certificate bridge landed
(2026-09-09). See `LAB_LOG.md`.
