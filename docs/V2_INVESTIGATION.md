# V2 Investigation Spec

**Production V1 stays frozen until these outputs exist.**

> Do not let aggregate decision means tell us where V1 failed until we know
> whether the evaluation itself has anomalous weeks.

---

## Protocol

```text
ANOMALY AUDIT (structural)
        │
        ▼
INSPECT TOP GAPS  (descriptive; never exclusion)
        │
        ▼
TAG weeks: clean | flagged | excluded
        │
   ┌────┴────┐
   ▼         ▼
NESTED     B0 GAP
HINDSIGHT  + substitutions
   │         │
   └────┬────┘
        ▼
   V1_GW1 counterfactual
        │
        ▼
   H0 / H1 / H2 / H3  →  V2A / V2B / both
```

---

## Evaluation status (circular-exclusion rule)

**Exclusion is defined only from evaluator/GW structure, never from V1 or B0 scores.**

| `evaluation_status` | Meaning |
|---|---|
| `clean` | 10 fixtures, actuals present, no structural flags |
| `flagged` | Real FPL week with structural oddity (BGW/DGW, a few duplicate GW rows) |
| `excluded` | Evaluator broken: missing actuals, join failure, pathological duplicates, solver failure |

**Never used to set `excluded`:** `V1 XI+Cap < 15`, `B0 XI+Cap > 80`, top B0−V1 gaps.

Those appear as `inspect_v1_lt_15` / `inspect_b0_gt_80` (descriptive only).

This circular-exclusion rule is the first formal invariant: changing model
predictions must not flip `evaluation_status`. See `docs/FORMAL.md`. Property
tests are queued as E012 (post-GW1, not a V2 gate).

DGWs/BGWs are **flagged**, not excluded, unless scoring is wrong.

---

## Two separate questions

**Hindsight nested regret** (actual points, evaluation only — not same-information):

```text
R_squad = P(hindsight-optimal 15+XI+cap) − P(oracle XI+cap | V1 15)
R_XI    = P(oracle XI+cap | V1 15) − P(V1 XI + best captain)
R_cap   = P(V1 XI + best captain) − P(V1 XI + V1 captain)
R_total = R_squad + R_XI + R_cap
          = P(oracle) − P(V1 realized)
```

**B0 gap:** `P(B0 XI+cap) − P(V1 XI+cap)` plus player substitutions.

Never collapse these into one metric.

The additive identity names this nested oracle. It is not an accounting of the
B0 gap. See `docs/FORMAL.md`.

---

## V1_GW1 diagnostic

Projections use production `horizon=6`. V1_6GW squad ILP uses `horizon_utility`; V1_GW1 uses `next_utility` on the same projections.
Default production path is unchanged (`objective="horizon"`).

| Outcome | Interpretation |
|---|---|
| Closes most of the **clean-week** gap | Objective mismatch matters for this test |
| Barely moves | Projection/minutes more important |
| Intermediate | H3: projection × discrete ILP |

A large `V1_GW1` lift is **not** a deploy decision. It means the evaluation objective and the 6-GW squad objective differ.

---

## Hypotheses

| ID | Claim |
|---|---|
| **H0** | Evaluation contamination / anomalous weeks dominate the mean |
| **H1** | Projection error |
| **H2** | Objective mismatch (horizon vs GW-N scoring) |
| **H3** | Small ranking errors amplified by discrete ILP + budget |

Test **H0 first**. H3 remains the interesting structural prior after the set is clean.

---

## Outputs

```text
records/historical/{season}/decision_gw.csv
records/historical/{season}/decision_decomp.csv
```

Mechanism columns on player rows are **diagnostic signatures**, not causes
(`horizon_flag`, `minutes_flag`, …). Summaries say “involves”, not “caused”.

Report **ALL / CLEAN / FLAGGED** with mean, median, P25, P75, 10% trimmed mean
for B0, V1, and V1_GW1.

---

```bash
python -m engine.harness_decomp --season 2025-26 --from-gw 1 --to-gw 38
python -m engine.harness_decomp --season 2024-25 --from-gw 1 --to-gw 38
```
