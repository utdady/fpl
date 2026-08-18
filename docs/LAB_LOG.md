# Experiment Log

Living record of hypotheses, tests, and results. **Append new experiments; do not rewrite old verdicts.** If a later test overturns an earlier one, add a new row and link back.

Related specs: `ROADMAP.md`, `docs/HARNESS_SPEC.md`, `docs/V2_INVESTIGATION.md`, `docs/V2_SPEC.md`.

Production V1 (`v1.0-gw1-baseline`) stays frozen until a gated experiment says otherwise.

---

## How to add a future test

1. Copy the template below into **Queued**, assign the next `E0xx` id.
2. When you run it, move it to **Completed**, fill Results / Verdict / Artifacts.
3. Update the **Hypothesis board** status (`open` / `supported` / `weak` / `rejected` / `contaminated`).
4. Do not delete old experiments. Note contamination instead.

### Template

```md
### E0xx — short title
- **Date:** YYYY-MM-DD
- **Status:** queued | running | completed
- **Hypothesis:** H?
- **Question:** one sentence
- **Method:** command / setup / information cutoff
- **Seasons / GWs:**
- **Metrics:**
- **Results:**
- **Verdict:**
- **Artifacts:**
- **Follow-up:**
```

---

## Hypothesis board

| ID | Claim | Status | Evidence |
|---|---|---|---|
| **H-audit-gk** | Backup GKs inherit starter minutes from old clubs | supported (qualitative) | V1 GW1 audit; `build_role_start` added before freeze |
| **H-audit-bench** | Equal 15-man sum undervalues premiums vs bench | supported (qualitative) | Pre-fix Haaland exclusion; `BENCH_WEIGHT=0.12` |
| **H-audit-guehi** | New-club minutes/role is a large LOO driver | supported (qualitative) | Guehi Δ ≈ 1.94, third-largest |
| **H-audit-haaland** | Forcing Haaland costs ~5 objective vs diversified 15 | supported (V1 objective) | Lock Δ = −4.86 vs baseline 15 |
| **H0** | Evaluation contamination / leaky B0 / anomalous weeks dominate decision *means* | **supported** | 2025/26 median V1 beats B0; B0 xP tracks actuals on blow-up GWs; 2024/25 B0 median ~97 |
| **H1** | Projection error (minutes, rates, fixtures) is the main *clean-week* problem | **open** | GW2 V1 XI had several 0-minute starters; not yet quantified across seasons |
| **H2** | 6-GW squad objective vs GW-N scoreboard explains the B0 gap | **weak** | `V1_GW1` vs `V1_6GW` ≈ +2 pts/GW; blow-ups unchanged |
| **H3** | Small μ errors × ILP × budget cause large XI jumps | **open** | Compatible with H0/H1; not isolated |
| **H-v1-naive** | V1 beats last-season points and naive pp90 at decision level | **supported** (with horizon=1 compare caveat) | E006 XI+Cap |
| **H-v1-xp** | V1 beats official xP (B0) at player MAE and XI+Cap | **not supported as stated** | E006 B0 wins means; E007 shows means are misleading and B0 may leak |

---

## Completed experiments

### E001 — Live V1 GW1 audit (2026/27)
- **Date:** 2026-08-18
- **Status:** completed
- **Hypothesis:** H-audit-*
- **Question:** Is the frozen V1 squad legal, and what drives it vs baselines?
- **Method:** `python fpl.py --refresh` then `python -m engine.audit --refresh`. Snapshot as of 2026-08-18 09:17 UTC. Strategy balanced, horizon 6.
- **Seasons / GWs:** 2026/27 GW1 (pre-deadline)
- **Metrics:** rule checklist, leave-one-out Δ, 15-man overlap vs ep_next / last-season / naive pp90, Haaland lock/exclude
- **Results:**
  - Squad legal, £100.0m, C B.Fernandes, VC Gabriel. Triple ARS/CHE/MUN.
  - Top GW1 xP: Haaland 7.39, Fernandes 7.03, Saka 6.71. Haaland **not** in 15.
  - Largest LOO Δ: Enzo 2.87, Gabriel 2.83, Guehi 1.94.
  - Baseline overlap with V1: ep_next 5/15, last-season 3/15, naive pp90 2/15.
  - Haaland lock costs 4.86 objective; locked 15 drops Fernandes + Saka.
- **Verdict:** V1 is a defensible GW1 control, with known minutes/new-club and no-captain-in-squad-objective limitations. Do not retune coefficients pre-deadline.
- **Artifacts:** live CLI output; tag `v1.0-gw1-baseline`
- **Follow-up:** E002 freeze; do not change V1 from audit findings

### E002 — Live GW1 prediction freeze (V1.5)
- **Date:** 2026-08-18
- **Status:** completed (freeze only; scoring waits for actuals)
- **Hypothesis:** capture before results or the live experiment is void
- **Question:** Can we serialise V1 GW1 μ/σ/p_start before kickoff?
- **Method:** `python -m engine.capture --gw 1` (no refresh; used cached snapshot)
- **Seasons / GWs:** 2026/27 GW1
- **Metrics:** row count, file exists
- **Results:** 590 player rows → `records/gw01_v1.0.csv` (~58.6 KB). Actuals empty until `--score`.
- **Verdict:** Live control captured.
- **Artifacts:** `records/gw01_v1.0.csv`
- **Follow-up:** after GW1 results, `python -m engine.capture --gw 1 --score`

### E003 — Harness validation (as-of-T)
- **Date:** 2026-08-18
- **Status:** completed
- **Hypothesis:** historical reconstruction can be made non-leaky enough to trust
- **Question:** Does `build_snapshot(season, as_of_gw=1)` contain only pre-GW1 information?
- **Method:** `python -m engine.harness_validate --season {2025-26,2024-25} --gw 1`
- **Seasons / GWs:** 2025/26 GW1, 2024/25 GW1
- **Metrics:** pass/fail gates (player count, ep_next excluded, minutes/points zero, opening prices, unfinished fixtures)
- **Results:** both seasons **PASS**. 2025/26: 841 players, 347 with rate signal, 10 unfinished GW1 fixtures. 2024/25: 804 players, 356 with rate signal.
- **Verdict:** GW1 harness is honest enough to score Test A. V2+ remains gated on *interpretation*, not on missing gates.
- **Artifacts:** CLI; spec in `docs/HARNESS_SPEC.md`
- **Follow-up:** rolling GW>1 validation is lighter (`--skip-validate` after GW1 pass)

### E004 — Test A: preseason GW1 historical score
- **Date:** 2026-08-18
- **Status:** completed
- **Hypothesis:** V1 preseason methodology has nonzero rank skill
- **Question:** If we had deployed V1 before 2025/26 and 2024/25 GW1, how good were player μ vs actuals?
- **Method:** `harness_run --gw 1` then `--score`. Prior-season rates + GW1 opening prices. `ep_next` excluded. Horizon 1 for this freeze.
- **Seasons / GWs:** 2025/26 GW1 (n=690); 2024/25 GW1 (n=616)
- **Metrics:** MAE, RMSE, bias, Spearman, p_start ECE, p_10 ECE
- **Results:**

  | Season | n | MAE | RMSE | Bias | Spearman | p_start ECE | p10 ECE |
  |---|---|---|---|---|---|---|---|
  | 2025/26 | 690 | 1.440 | 2.448 | +0.430 | 0.385 | 0.095 | 0.014 |
  | 2024/25 | 616 | 1.260 | 2.101 | +0.361 | 0.367 | 0.127 | 0.009 |

- **Verdict:** Weak but positive rank correlation. Bias slightly high (over-prediction of blanks). Not a decision-level test.
- **Artifacts:** `records/historical/{season}/gw01_v1.0.csv`, `scores.csv`
- **Follow-up:** E005 rolling; E006 baselines

### E005 — Test B: rolling GW1–38 V1 freeze + score
- **Date:** 2026-08-18
- **Status:** completed
- **Hypothesis:** as-of-T rolling update works without future leakage in the record files
- **Question:** Can we freeze and score V1 for every GW in both completed seasons?
- **Method:** `harness_run --from-gw 2 --to-gw 38 --skip-existing --skip-validate` then `--score`. Snapshot uses stats through GW N−1. Horizon 1 in these record files.
- **Seasons / GWs:** 2024/25 and 2025/26, GW1–38
- **Metrics:** files written; per-GW MAE/Spearman in `scores.csv`
- **Results:** 38/38 GWs frozen and scored each season. 2025/26 MAE drifts from 1.44 (GW1) toward ~1.0 late season; Spearman rises from ~0.39 to ~0.60. Similar pattern in 2024/25 (GW1 Spearman 0.37 → GW38 0.69).
- **Verdict:** Rolling capture pipeline works. Late-season Spearman improvement is expected (current-season minutes in the snapshot) and is **not** by itself evidence that preseason V1 is strong.
- **Artifacts:** `records/historical/{season}/gw{nn}_v1.0.csv`, `scores.csv`
- **Follow-up:** E006 decision-level baselines; note these records are horizon-1 projections

### E006 — B0–B3 comparison (player + XI+Cap)
- **Date:** 2026-08-18
- **Status:** completed (caveat below)
- **Hypothesis:** H-v1-naive, H-v1-xp
- **Question:** Does V1 beat official xP / last-season points / naive pp90 on MAE and on ILP XI+captain actuals?
- **Method:** `python -m engine.harness_compare --season … --from-gw 1 --to-gw 38`. **V1 projected with horizon=1**, so squad ILP utility ≈ next-GW μ. B0 = Vaastav `xP` (possible timing leakage).
- **Seasons / GWs:** both seasons, 38 GWs, **means only** (no anomaly split)
- **Metrics:** player MAE/RMSE/Spearman; XI+Cap (captain doubled)
- **Results (season mean):**

  | Model | 2025/26 MAE | 2025/26 Spearman | 2025/26 XI+Cap | 2024/25 MAE | 2024/25 Spearman | 2024/25 XI+Cap |
  |---|---|---|---|---|---|---|
  | B0 xP | 1.070 | 0.520 | 40.89 | 0.928 | 0.694 | 89.03 |
  | B1 season pts | 1.795 | 0.542 | 32.55 | 1.768 | 0.493 | 43.45 |
  | B2 pp90 | 1.546 | 0.564 | 28.92 | 1.668 | 0.487 | 37.45 |
  | B3 V1 | 1.103 | 0.536 | 36.26 | 1.139 | 0.492 | 45.24 |

- **Verdict:**
  - V1 **beats B1 and B2** on XI+Cap in both seasons → H-v1-naive supported.
  - V1 **does not beat B0** on these *means* → H-v1-xp not supported as stated.
  - 2024/25 B0 XI+Cap mean 89 / Spearman 0.69 is **not a fair ceiling** until leakage is bounded (feeds H0).
  - 2025/26 MAE gap vs B0 is tiny (0.033) vs XI+Cap gap (4.63) — but E007 shows that XI+Cap *mean* is dominated by a few weeks.
- **Artifacts:** `records/historical/{season}/b0_b3_comparison.csv`
- **Follow-up:** E007; do not use E006 means as the V2A/V2B decision

### E007 — Anomaly audit + nested regret + V1_GW1 (horizon 6)
- **Date:** 2026-08-18
- **Status:** completed
- **Hypothesis:** H0, H1, H2, H3
- **Question:** After tagging weeks structurally, where does V1 lose points, and does GW-myopic squad selection close the B0 gap?
- **Method:** `python -m engine.harness_decomp --season … --from-gw 1 --to-gw 38`. V1 projected **horizon=6**. `V1_GW1` = same μ, squad ILP `objective=next`. Exclusion **never** uses V1/B0 scores. DGW actuals summed; 1–5 identical junk rows ignored.
- **Seasons / GWs:** 2024/25, 2025/26, GW1–38. Excluded = 0 both seasons.
- **Metrics:** ALL/CLEAN/FLAGGED mean, median, P25/P75, trim10; nested hindsight regret share; top B0−V1 gaps (inspection only)

- **Results — 2025/26:**

  | Slice | n | B0 median | V1 median | V1_GW1 median | vs B0 gap mean / median |
  |---|---|---|---|---|---|
  | ALL | 38 | 22 | 38.5 | 43.5 | +3.0 / −10.5 |
  | CLEAN | 33 | 22 | 36 | 34 | +9.9 / −8.0 |
  | FLAGGED | 5 | 17 | 68 | 71 | −42 / −41 |

  Hindsight share (ALL): squad 86.5% / XI 8.3% / cap 5.3%.  
  `V1_GW1` − `V1` ≈ **+2 pts/GW**. Top gaps are **clean 10-fixture** weeks (GW2/6/8: B0 118–121 vs V1 10–13).  
  GW2 sample: B0 xP ≈ actuals (Calafiori 14→13, Timber 13→24); V1 XI included 0-point Wissa/Isak/Travers.

- **Results — 2024/25:**

  | Slice | n | B0 median | V1 median | V1_GW1 median | vs B0 gap mean / median |
  |---|---|---|---|---|---|
  | ALL | 38 | 97 | 43.5 | 51 | +47.6 / +52 |
  | CLEAN | 31 | 97 | 41 | 43 | +53.6 / +53 |
  | FLAGGED | 7 | 101 | 67 | 72 | +21 / +49 |

  `V1_GW1` − `V1` ≈ **+3 pts/GW**. B0 median ~97 on clean weeks is not a plausible non-leaky projection baseline.

- **Verdict:**
  - **H0 supported.** Do not let E006 decision *means* pick V2A vs V2B.
  - **H2 weak** for this scoreboard: GW-myopic squad does not fix blow-ups.
  - **H1/H3 still open.** Next work is minutes/availability and B0-xP-vs-actual correlation by GW — still no production V1 change.
  - Hindsight “86% squad” is vs god-mode 15, **not** the B0 gap. Do not quote it as “optimizer is the B0 problem.”
- **Artifacts:** `records/historical/{season}/decision_gw.csv`, `decision_decomp.csv`; `docs/V2_INVESTIGATION.md`
- **Follow-up:** E008 B0 leakage bound; E009 V1 zero-minute XI audit

---

## Queued

### E008 — B0 xP vs actual correlation by GW
- **Date:** —
- **Status:** queued
- **Hypothesis:** H0 (leakage)
- **Question:** On which GWs is Vaastav `xP` so correlated with actual points that B0 is a near-oracle?
- **Method:** Spearman(xP, actual) per GW; flag GWs with r above a pre-registered threshold (propose 0.70). Do **not** exclude those GWs from V1 metrics using V1 scores.
- **Seasons / GWs:** both, 1–38
- **Metrics:** per-GW Spearman; share of GWs above threshold
- **Results:** —
- **Verdict:** —
- **Artifacts:** proposed `records/historical/{season}/b0_leakage.csv`
- **Follow-up:** if many GWs exceed threshold, stop using B0 XI+Cap as a V2 gate

### E009 — V1 XI players with 0 actual minutes
- **Date:** —
- **Status:** queued
- **Hypothesis:** H1 (minutes / availability)
- **Question:** What fraction of V1 XI slots (clean GWs) go to players who played 0 minutes, and is that predicted p_start high?
- **Method:** join `decision_decomp.csv` where `in_v1_xi=1` to actual minutes; report rates vs B0 XI
- **Seasons / GWs:** both, CLEAN only for headline; ALL as sensitivity
- **Metrics:** % XI slots with 0 minutes; mean p_start of those slots
- **Results:** —
- **Verdict:** —
- **Artifacts:** proposed `records/historical/{season}/minutes_miss.csv`
- **Follow-up:** if high, V2A minutes/role is first investment

### E010 — Live 2026/27 GW1 score
- **Date:** after GW1 results (deadline 2026-08-21 17:30 UTC)
- **Status:** queued
- **Hypothesis:** live control is scoreable
- **Question:** What is frozen V1’s player-level scorecard on real GW1?
- **Method:** `python -m engine.capture --gw 1 --score`
- **Seasons / GWs:** 2026/27 GW1
- **Metrics:** MAE, RMSE, bias, Spearman, ECE
- **Results:** —
- **Verdict:** —
- **Artifacts:** `records/gw01_v1.0.csv`, `records/scores.csv`
- **Follow-up:** do not retune V1 from one GW

### E011 — Test C: full-season decision simulation
- **Date:** —
- **Status:** queued (blocked on V2B/V5 scope)
- **Hypothesis:** optimizer-managed transfers beat naive one-GW squads
- **Question:** With 1 FT/week, does V1’s 15 accumulate more season points than B1/B2 (and B0 if non-leaky)?
- **Method:** not started. Requires transfer engine; not E007.
- **Seasons / GWs:** —
- **Metrics:** season points, hits, captain points
- **Results:** —
- **Verdict:** —
- **Artifacts:** —
- **Follow-up:** after V2 investigation chooses V2A/V2B

---

## Current call (do not skip this when adding tests)

As of 2026-08-18:

1. Live V1 is frozen and GW1 predictions are captured.
2. Historical harness GW1 gates passed on 2024/25 and 2025/26.
3. V1 beats naive baselines on E006 XI+Cap; it does **not** beat B0 on E006 *means*.
4. E007: those means are the wrong statistic. On 2025/26, **median** V1 XI+Cap beats B0. Blow-up weeks are structurally clean and look like leaky xP plus V1 minutes misses.
5. `V1_GW1` is not a production change and does not close blow-ups (**H2 weak**).
6. **Next:** E008 and E009. Still **no production V1 change**.

---

## Index of commands

```bash
# Live
python fpl.py --refresh
python -m engine.audit --refresh
python -m engine.capture --gw 1
python -m engine.capture --gw 1 --score

# Harness
python -m engine.harness_validate --season 2025-26 --gw 1
python -m engine.harness_run --season 2025-26 --from-gw 1 --to-gw 38 --skip-existing
python -m engine.harness_run --season 2025-26 --from-gw 1 --to-gw 38 --score --skip-existing
python -m engine.harness_compare --season 2025-26 --from-gw 1 --to-gw 38
python -m engine.harness_decomp --season 2025-26 --from-gw 1 --to-gw 38
```
