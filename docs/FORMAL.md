# Formal integrity

> **Lean can prove that our experiment means what we say it means. It cannot prove that our data is truthful.**
>
> Python tells us what happened. Statistics tell us whether it is reproducible. Lean tells us whether we accidentally changed the question while measuring it.

This is a **post-GW1** track. It is not a V2 gate. Production V1 (`v1.0-gw1-baseline`) stays frozen. The next research lever remains V2A-M (minutes / availability). See `LAB_LOG.md`, `HARNESS_SPEC.md`, `V2_INVESTIGATION.md`.

---

## Division of labour

```text
                  FPL RESEARCH SYSTEM
                         |
          +--------------+--------------+
          |                             |
       Python                         Lean
          |                             |
   empirical science             formal integrity
          |                             |
   projections                   dependency rules
   minutes                      regret identities
   fixtures                     evaluation invariants
   backtests                     snapshot types
   optimization                 legality/certificates
   calibration
          |                             |
          +--------------+--------------+
                         |
                         v
                  TRUSTWORTHY RESULTS
```

| Question | Tool |
|---|---|
| Is every optimizer output legal? | Yes — later, as a certificate check |
| Does captain doubling apply correctly? | Yes — later |
| Does a predictor *type* exclude future fields? | Yes |
| Do scoring and regret mean what we claim? | Yes |
| Is `P(start)=0.9` calibrated? | No — empirical (E009) |
| Does V2 beat V1? | No — empirical |
| Is Vaastav `xP` leaked? | Provenance / Spearman (E008), not a type theorem |
| Is Haaland optimal? | No — model-dependent |

Lean is not used to prove football. It is used to protect definitions and dependency graphs.

---

## Three dependency graphs

Do not collapse these into one "no extra information" rule.

| Artifact | May depend on | Must not depend on |
|---|---|---|
| `predict(Snapshot T)` | fields permitted at cutoff T | actuals at T or later; any post-deadline column |
| `LeakFlag` | B0 `xP` and actuals | V1 / V2 / any challenger scores |
| `evaluation_status` | fixtures, integrity, structure, and (if chosen) `LeakFlag` | model error, MAE, XI+Cap, regret |

`LeakFlag = h(xP, actual)` is **evaluation-time** classification. It may see actuals. The snapshot theorem is the one that forbids actuals. If those two are collapsed, E008 becomes unstateable.

Pre-registered E008 rule: **Spearman(xP, actual) > 0.70**, from xP vs actual only, never from V1 scores.

`evaluation_status` (`clean` / `flagged` / `excluded`) is structural. Changing model predictions must not flip a week's status. Never set `excluded` from `V1 XI+Cap < 15` or `B0 XI+Cap > 80`.

---

## Identical feasible set is not identical experiment

For a fair model compare, every challenger shares the same legal set F (15-man, budget, positions, club limit, XI formation).

Horizon, objective U, and scoring g are **separate declarations**.

`V1_GW1` is a valid counterfactual: same mu, different U (`next` vs 6-GW horizon). A formal module that requires "same objective" would forbid the test that weakened H2.

---

## Regret identity names its oracle

Nested hindsight on the **same actuals**:

```text
R_squad = P(hindsight-optimal 15+XI+cap) - P(oracle XI+cap | V1 15)
R_XI    = P(oracle XI+cap | V1 15) - P(V1 XI + best captain)
R_cap   = P(V1 XI + best captain) - P(V1 XI + V1 captain)
R_total = R_squad + R_XI + R_cap
        = P(oracle) - P(V1 realized)
```

This identity is relative to the god-mode nested oracle, **not** the B0 gap.

E007: hindsight share 86.5% / 8.3% / 5.3% is vs god-mode 15. Do not quote it as "the optimizer is the B0 problem."

B0 gap: `P(B0 XI+cap) - P(V1 XI+cap)` plus substitutions. Never collapse the two.

---

## Type-level cutoff vs provenance

Two layers, both required:

```text
PROVENANCE / RECONSTRUCTION     type-level Snapshot<T>
        +                              +
   was this column honest?        can the predictor even see it?
```

A well-typed `Snapshot<GW5>` can still contain contaminated `xP`. Lean proves the predictor has no parameter for GW6 actuals. It does not prove the CSV loaded into allowed fields was pre-deadline.

Field-level reconstruction and validation gates live in `HARNESS_SPEC.md`. E008 is the empirical leakage check on B0.

---

## What we will not formalize

- Solver optimality of CBC / PuLP. Python returns a candidate; a later checker may verify legality and reconstructed objective. Do not verify CBC.
- Calibration, MAE, "V2 is better," "Haaland is optimal."
- Minutes overconfidence: E009 has P(start) in [0.90, 1.00] at 79.4% start / 18.6% 0-min (2025/26). That is V2A-M, not Lean.

---

## Post-GW1 sequence

Not a version gate. Do not block V2A-M on this.

```text
POST-GW1
    |
    v
Property tests
    |
    +-- anomaly independence
    +-- leakage-flag independence
    +-- identical feasible set F
    +-- regret decomposition identity
    |
    v
Lean core (formal/)
    |
    +-- Evaluation.lean
    +-- Leakage.lean
    +-- Regret.lean
    +-- Snapshot.lean
    |
    v
Optional certificate checker   (only if legality becomes a recurring concern)
    |
    v
Squad / Lineup formalization
```

Property tests come first. They are the executable invariant. Lean polishes the same claims.

Suggested first tests (after GW1, not before):

1. Shuffle or replace V1/V2 predictions; `evaluation_status` labels must be identical.
2. Recompute `LeakFlag` after mutating V1 scores; flags must be identical.
3. Assert `R_total == R_squad + R_XI + R_cap` on every scored GW (named oracle).
4. Assert B0 / V1 / V2 ILPs use the same constraint set F when compared.

---

## Implementation inventory

Living record of what `formal/` contains. Update when a module lands or scope
changes. Do **not** log CI plumbing here — git history covers that.

| Module | Formalizes | Python source | Lean artifact | Python regression |
|---|---|---|---|---|
| `Regret.lean` | Nested regret is additive: `R_total = P(oracle) − P(V1 realized)`; B0 gap is separate | `engine.harness_decomp.evaluate_gw` | `regret_identity_int`; `B0Gap` struct | `TestRegretIdentity` |
| `Evaluation.lean` | `evaluation_status` from fixture count + integrity only; never `inspect_*` | `engine.harness_decomp.classify_week` | `classifyWeek` port; `joinFloor` | `TestEvaluationStatusIndependence` |
| `Leakage.lean` | `LeakFlag` depends only on xP + actuals (evaluation-time) | `engine.obs.LEAKAGE_SPEARMAN` | `LeakInput`; `leakFlag`; Spearman `opaque` | `TestLeakFlagIndependence` |
| `Snapshot.lean` | Predictor at GW `n` cannot take `Actuals` in its signature | `engine.models.Snapshot`; `HARNESS_SPEC.md` | `Snapshot gw`, `Predictor gw`, `Actuals gw` | `engine.harness_validate` (provenance) |

**Evaluation note:** `joinFloor(nSnapshot) = max(50, ⌊0.15 · nSnapshot⌋)`. Status labels
depend on snapshot size as well as integrity fields — not on model scores.

### Queued

| Module | Formalizes | Python source | Status |
|---|---|---|---|
| `Squad.lean` | Legal 15: size, budget, positions, club limit | `engine.optimize.solve_squad` | not started |
| `Lineup.lean` | Legal XI formation windows | `engine.optimize.solve_xi` | not started |
| Certificate checker | Verify returned squad + objective; not CBC optimality | `engine.optimize` | not started |

**Authority:** `tests/test_e012_integrity.py` remains the regression harness on recorded
artifacts. Lean makes definitions and identities explicit; it is not a V2 gate.

---

**Status (E012):** Python property tests **PASS** — `tests/test_e012_integrity.py` (9/9).
Lean core **landed** in `formal/` (see Implementation inventory above). CI: `.github/workflows/formal.yml`.
Build: `cd formal && lake build` (requires [elan](https://github.com/leanprover/elan)).
Milestone: **E012-lean** in `LAB_LOG.md`.

Queued historically as **E012** in `LAB_LOG.md`.
