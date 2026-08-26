# Experiment Log

Living record of hypotheses, tests, and results. **Append new experiments; do not rewrite old verdicts.** If a later test overturns an earlier one, add a new row and link back.

Related specs: `ROADMAP.md`, `docs/HARNESS_SPEC.md`, `docs/V2_INVESTIGATION.md`, `docs/V2_SPEC.md`, `docs/FORMAL.md`.

**Production (post E015 promote):** `minutes_version=v2am_s` (`v2am-s-baseline`).  
**Permanent historical control:** V1 (`v1.0-gw1-baseline`) — harnesses pin `minutes_version=v1`.  
**Active research question:** E017 prior→XI dampening pre-registered (`rates=v2b_d`, α=0.50). E016 REJECT stands; minutes locked.

---

## Two freezes (pre-registered 2026-08-18, before E008/E009)

**Production freeze (GW1 era)** — V1.0 projection, minutes, fixtures, coefficients, optimizer, objective. Generated the Friday GW1 team. Superseded for *live* production by `v2am-s-baseline` after E015; V1 remains the permanent historical benchmark.

**Research calendar** — Historical Lab, E008, E009, conditional MAE, decomposition, V2 spec. May run anytime. Informed **post-GW1** development.

> Research can change our beliefs before GW1. It cannot change the frozen experiment.

### Friday default squad (timestamped before E008/E009)

Default = V1 balanced 15 from the freeze snapshot (`engine.audit` 2026-08-18 09:17 UTC / `records/gw01_v1.0.csv` projections).

- **Guehi: IN** (V1 selected him). No `must_exclude`.
- **Haaland: OUT** (V1 did not select him). No `must_include`.
- **Human overlay: none.**

If E009 is ugly, that is V2 evidence. It does not exclude Guehi on Thursday.

### E008 / E009 authority

| May modify | May NOT modify | May inform |
|---|---|---|
| Hypotheses, V2 priorities, post-GW1 plan | V1.0 production code | Already-scoped human lock/exclude **only if written before these queries** (none were) |
| | Frozen `records/gw01_v1.0.csv` | |
| | Friday default squad | |

Pre-registered leakage flag: **Spearman(xP, actual) > 0.70**, from xP vs actual only, never from V1 scores.

| Finding | Friday |
|---|---|
| H0a strong | No change. B0 is not a V2 gate. |
| H0a weak | No change. V2 signal only. |
| **H0a weak and H0b strong** | **No change.** Ship frozen V1. That is the experiment. |
| E009 ugly / Guehi-type general | No change to code or default 15. |

H2 (from E007): **weak / not the primary lever.** Evidence is that blow-up weeks survived the `V1_GW1` counterfactual, not the 36→34 median shift alone.


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
| **H0** | Evaluation contamination / leaky B0 / anomalous weeks dominate decision *means* | **supported** | E007 medians; E008 |
| **H0a** | Vaastav xP has post-deadline / near-oracle information on some GWs | **supported** (esp. 2024/25) | E008: 10/38 GWs 2025/26 and **34/38** 2024/25 have Spearman(xP,actual)>0.70; flagged set includes 2025/26 blow-ups GW2–6,8,9 |
| **H0b** | Historical V1 is missing legitimate pre-deadline minutes/availability | **supported at XI layer** | E009: V1 XI 0-min slots 29% (2025/26) / 16% (2024/25) |
| **H1** | Projection *rate* error (xG/xA/fixture) is the main clean-week problem | **not first lever** | E009: MAE minutes>=60 is *higher* than <60 (variance among those who play); XI blanks are the sharper miss |
| **H2** | 6-GW squad objective vs GW-N scoreboard explains the B0 gap | **weak / not the primary lever** | Blow-up weeks survived `V1_GW1`; 36→34 median on n=33 is not killing evidence |
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
  - **H2 weak / not the primary lever:** blow-up weeks survived `V1_GW1`. Do not treat 36→34 as a formal reject.
  - **H1/H3 still open.** Next work is minutes/availability and B0-xP-vs-actual correlation by GW — still no production V1 change.
  - Hindsight “86% squad” is vs god-mode 15, **not** the B0 gap. Do not quote it as “optimizer is the B0 problem.”
- **Artifacts:** `records/historical/{season}/decision_gw.csv`, `decision_decomp.csv`; `docs/V2_INVESTIGATION.md`
- **Follow-up:** E008/E009 completed same day; see below

---

### E008 — B0 xP vs actual correlation by GW
- **Date:** 2026-08-18
- **Status:** completed (observational; after Friday-squad pre-registration above)
- **Hypothesis:** H0a
- **Question:** On which GWs is Vaastav `xP` so correlated with actuals that B0 is a near-oracle?
- **Method:** `python -m engine.obs --season …`. Spearman(xP, actual) per GW. Flag **pre-registered** at r > 0.70 from xP vs actual only.
- **Seasons / GWs:** both, 1–38
- **Metrics:** per-GW Spearman, MAE, bias; count of flagged GWs
- **Results:**

  | Season | Flagged (r>0.70) | Spearman mean / median | min / max | Flagged GWs include blow-ups? |
  |---|---|---|---|---|
  | 2025/26 | **10/38** | 0.555 / 0.484 | 0.435 / 0.829 | Yes: 2, 3, 4, 5, 6, 8, 9 (+24, 29, 38) |
  | 2024/25 | **34/38** | 0.718 / 0.747 | 0.364 / 0.813 | Almost the whole season |

- **Verdict:** **H0a supported.** 2024/25 B0 is not a competitive baseline. 2025/26 is two-regime: ordinary GWs look like a normal predictor; the E007 blow-up weeks are exactly the high-Spearman set. Stop using B0 XI+Cap as a V2 *gate*. Still usable as an upper-bound diagnostic. **Friday squad unchanged** (pre-registered).
- **Artifacts:** `records/historical/{season}/b0_leakage.csv`
- **Follow-up:** reconstruct non-leaky official xP only if needed post-GW1; do not chase B0 for Friday

### E009 — Minutes calibration, XI 0-min, conditional MAE
- **Date:** 2026-08-18
- **Status:** completed (observational)
- **Hypothesis:** H0b / H1 minutes vs rates; Guehi-type vs general
- **Question:** Is V1 p_start calibrated, do XI slots go to 0-minute players, and is that a new-club effect? Is MAE among 60+ minute players the rate bottleneck?
- **Method:** `python -m engine.obs`. Player-level tables from frozen `gw{nn}_v1.0.csv`. New-club = different/missing prior-season team via Vaastav `code`. XI 0-min from `decision_decomp.csv` + `gw_actuals`.
- **Seasons / GWs:** both, 1–38
- **Metrics:** start% and 0-min% by p_start bucket; XI 0-min rate; MAE | minutes>=60 vs <60

- **Results — p_start calibration (all players):**

  2025/26

  | P(start) | n | actual start% | 0-min% | avg pts |
  |---|---|---|---|---|
  | 0.90–1.00 | 773 | 79.4 | 18.6 | 2.92 |
  | 0.80–0.90 | 962 | 74.4 | 19.5 | 2.93 |
  | 0.70–0.80 | 227 | 46.3 | 37.9 | 2.15 |
  | 0.60–0.70 | 1455 | 67.0 | 20.2 | 2.84 |
  | <0.60 | 25921 | 23.3 | 66.7 | 0.93 |

  2024/25 0.90–1.00: start 83.9%, 0-min 14.4%.

- **New-club vs established (p_start 0.90–1.00, player-GW rows):**

  | Season | split | n | start% | 0-min% |
  |---|---|---:|---:|---:|
  | 2025/26 | established | 299 | 75.9 | 23.1 |
  | 2025/26 | new_club | 474 | 81.6 | 15.8 |
  | 2024/25 | established | 361 | 79.5 | 19.1 |
  | 2024/25 | new_club | 249 | 90.4 | 7.6 |

  Comparison is **confounded** (selection into high p_start bucket differs by group). n is large enough in 2025/26 that naive readings can mislead; it does **not** identify transfer status as the cause. **No generic new-club prior in V2A-M v1.** Guehi stays a human GW1 decision / post-GW1 case study.


- **V1 XI 0-minute slots:**

  | | 2025/26 | 2024/25 |
  |---|---|---|
  | ALL | 122/418 = **29.2%** | 69/418 = 16.5% |
  | CLEAN | 115/363 = **31.7%** | 65/341 = 19.1% |
  | new-club slots | 28.4% | 21.7% |
  | established slots | 30.2% | 12.6% |

- **Conditional MAE:**

  | | 2025/26 MAE | 2024/25 MAE |
  |---|---|---|
  | minutes >= 60 | 2.662 (n=7709) | 2.423 (n=7718) |
  | minutes < 60 | 0.544 (n=21629) | 0.631 (n=19513) |

  Higher MAE among those who played is expected (real point variance). It does **not** mean “fix xG first.” The decision-level miss is XI blanks.

- **Verdict:** **H0b supported at the XI layer** (~30% of 2025/26 V1 XI slots played 0 minutes). Top-bucket p_start is overconfident (~80% start when we claim 90%+). New-club split **unresolved/confounded** — cite only with n (see table above). V2A-M first target after GW1: **minutes/availability feeding the 15**, not optimizer, not Guehi-only. **Friday: Guehi stays; no minutes.py change.**
- **Artifacts:** `records/historical/{season}/minutes_cal.csv`
- **Follow-up:** post-GW1 minutes model (role/availability). Do not retune before deadline.
- **Output:** obs.py prints explicit tail-bucket n summary (established vs new_club) on every run.

## Queued

### E013 - Four-season robustness panel
- **Date:** 2026-08-19 (pre-registered); full panel run same day (research calendar; **does not** change Friday control)
- **Status:** completed
- **Hypothesis:** H0a, H0b, H2, H-v1-naive - qualitative verdicts reproduce across regimes
- **Question:** Do B0 leakage, high-`p_start` overconfidence, XI blanks, and weak horizon mismatch hold on 2022/23 and 2023/24?
- **Method:** Extended `SUPPORTED_SEASONS` to 2022-2025. Per season: E003 -> E005 -> E006 -> E007 -> E008/E009. Logistic cal fit on `p_start >= 0.60`. Synthesis via `scripts/e013_synthesis.py`.
- **Seasons / GWs:** 2022/23, 2023/24, 2024/25, 2025/26 x GW1-38 (2022/23 GW7 missing Vaastav actuals; decomp n=37)
- **Caveats:**
  - 2022/23 prior season (2021/22) has no `expected_goals` in Vaastav - harness uses goals/assists as rate proxy for GW1 reconstruction only
  - V1 DC scoring in projections; older seasons lack DC in Vaastav actuals - player MAE less comparable; minutes/XI gates still valid
  - E006 `xi_points` already includes captain double-count; compare column uses `xi_points` mean

- **Synthesis table:**

  | Season | B0* flagged GWs | Tail n | Start% @ >=0.90 | XI 0-min % (ALL) | V1_GW1-V1 mean (CLEAN) | V1 XI+Cap | B1 | B2 | V1>B1 | V1>B2 | alpha / beta (p>=0.60) | P@0.90 fit |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
  | 2022/23 | 33/38 | 563 | 84.0 | 27.0 | -0.48 | 45.1 | 43.6 | 36.9 | yes | yes | 0.646 / 0.261 | 77.2 |
  | 2023/24 | 31/38 | 645 | 78.5 | 25.1 | +1.63 | 44.4 | 36.8 | 33.0 | yes | yes | 0.568 / 0.242 | 75.0 |
  | 2024/25 | 34/38 | 610 | 83.9 | 16.5 | +2.55 | 45.2 | 43.4 | 37.4 | yes | yes | 0.680 / 0.205 | 75.6 |
  | 2025/26 | 10/38 | 773 | 79.4 | 29.2 | +1.45 | 36.3 | 32.6 | 28.9 | yes | yes | 0.330 / 0.414 | 77.6 |

- **Verdict (qualitative panel):**
  - **H0a supported** - B0 flagged in all four seasons (10-34/38 GWs). Never a V2 gate.
  - **H0b supported** - `p90_fitted` (actual start rate at model >= 0.90) is ~75-78% across all four seasons; that is the stable headline, not the raw alpha/beta parameters which trade off against each other. Logistic beta << 1 everywhere -> nonlinear tail compression; prefer bucket recalibration over a single multiplicative shrink. **alpha/beta are diagnostic appendix only.**
  - **2024/25 XI 0-min (16.5%) is an outlier** vs the other three seasons (25-29%), not the low end of a continuum. Cause unexplained (fewer transfer disruptions? DGW mix?). V2A-M gates should evaluate all four seasons individually, not assume a 16-29% uniform range.
  - **H2 weak / indistinguishable from noise** - `V1_GW1 - V1` is +1.5 to +2.6 pts/GW (CLEAN) in 2023-2025 but **-0.48 in 2022/23**. Inconsistent sign across seasons = no stable directional effect; this is the correct reason to shelve the horizon objective, not rounding the negative case to zero.
  - **H-v1-naive supported** - V1 XI+Cap beats B1 and B2 all four seasons.
  - **New-club prior** - still unresolved/confounded; cite with n only; alpha/beta split-level fits show sign flips (e.g. 2022/23 established beta~1.0 vs new_club beta~-0.04) confirming those parameters are noise-sensitive and should never inform design decisions.
  - **V2A-M justification (canonical statement):** V1's repeatable weakness is upper-tail playing-time overconfidence, which propagates into XI blank selections; it is not currently supported as generic transfer mispricing or an optimizer-objective failure. Stable evidence: p90_fitted ~75-78%, XI 0-min elevated in 3/4 seasons. Target minutes/availability.

- **Artifacts:** `records/historical/{2022-23,2023-24}/` full harness set; `minutes_cal_fit.csv` on all four seasons; `scripts/e013_synthesis.py`
- **Follow-up:** implement V2A-M post-GW1 using this panel as gate evidence. Friday squad unchanged.


### E010 - Live 2026/27 GW1 score
- **Date:** 2026-08-25
- **Status:** completed
- **Hypothesis:** live control is scoreable; do not retune V1 from one GW
- **Question:** What is frozen V1's player-level scorecard on real GW1, and did the Friday 15 / Guehi decision look like the historical failure modes?
- **Method:** `python -m engine.capture --gw 1 --score` against FPL `event/1/live/`. Squad reconstruction from frozen mus + freeze-time costs via `solve_squad` (eligibility from post-deadline cache; composition matches pre-reg: Guehi IN, Haaland OUT).
- **Seasons / GWs:** 2026/27 GW1 (n=590)

- **Results - player scorecard:**

  | Metric | Live GW1 | Hist GW1 2025/26 | Hist GW1 2024/25 |
  |---|---:|---:|---:|
  | MAE | **1.621** | 1.440 | 1.260 |
  | RMSE | 2.682 | 2.448 | 2.101 |
  | Bias | +0.047 | +0.430 | +0.361 |
  | Spearman | **0.481** | 0.385 | 0.367 |
  | p_start ECE | 0.113 | 0.095 | 0.127 |
  | p_10 ECE | 0.016 | 0.014 | 0.009 |

- **Results - P(start) calibration (live GW1):**

  | bucket | n | start% | 0min% |
  |---|---:|---:|---:|
  | 0.90-1.00 | 60 | 85.0 | 11.7 |
  | 0.80-0.90 | 44 | 65.9 | 18.2 |
  | 0.60-0.70 | 56 | 50.0 | 23.2 |
  | <0.60 | 425 | 25.4 | 60.7 |

  Top bucket (85%) is within / slightly above the E013 four-season band (~78-84%). One GW is not a recalibration.

- **Results - reconstructed V1 XI+Cap:** XI 37 + Saka C 9 = **46**. XI 0-min slots **3/11 = 27.3%** (Martinez, Gyokeres, Welbeck) - sits in the 25-29% historical cluster, not the 2024/25 outlier. Enzo: model p_start=0.90, actual 25 minutes (classic upper-tail miss inside the XI).

- **Guehi case study (one week, not a model rule):** Guéhi started, 90 minutes, **10 points**. Haaland (OUT of Friday 15) started 90 minutes but scored only **2**. Neither outcome authorizes a transfer prior or a production change - E013 already forbids that leap. Panel validates the *category*; E010 is one draw from it.

- **Verdict:** Live control is scoreable. Rank skill present (Spearman 0.48). Minutes/XI-blank failure mode appeared on schedule (~27% XI blanks). **Do not retune V1 from GW1.** Next: V2A-M.
- **Artifacts:** `records/gw01_v1.0.csv` (scored), `records/scores.csv`
- **Follow-up:** V2A-M implementation; E012 property tests in parallel. No production V1 change.


### E014 - V2A-M LOSO minutes recalibration
- **Date:** 2026-08-26
- **Status:** completed - **REJECT as production replacement**
- **Hypothesis:** Upper-tail p_start overconfidence is largely a calibration map problem fixable without rates/fixtures/ILP changes
- **Question:** Does leave-one-season-out bucket remapping of V1 `p_start` improve upper-tail reliability, cut XI 0-min rate, and raise XI+cap vs V1, without hurting MAE_60+?
- **Method:** `python -m engine.harness_v2am`. LOSO empirical start rate per V1 bucket applied inside `project_all(..., minutes_version=v2am)`. No new-club prior. Production default remains `v1`.
- **Seasons / GWs:** 2022/23-2025/26, GW1-38

- **Results:**

  | Season | ut_gap V1 | ut_gap V2 | XI0 V1 | XI0 V2 | XI+Cap V1 | XI+Cap V2 | MAE60 V1 | MAE60 V2 |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|
  | 2022/23 | 0.101 | **0.035** | 27.0% | 26.3% | 46.4 | **49.1** | 2.665 | 2.634 |
  | 2023/24 | 0.121 | **0.037** | 25.1% | 27.5% | 44.4 | 44.2 | 2.534 | 2.489 |
  | 2024/25 | 0.113 | **0.035** | **16.5%** | 21.5% | 45.2 | **47.9** | 2.423 | 2.415 |
  | 2025/26 | 0.097 | **0.026** | 29.2% | 33.7% | 36.3 | 36.4 | 2.662 | 2.666 |

- **Gate calls:**
  - Upper-tail gap: **PASS** all four seasons (reliability of confidence labels improves)
  - XI 0-min: **FAIL** - worse or flat in 3/4 seasons (cheat-block); only trivial help in 2022/23
  - XI+Cap: **mixed** - clear wins in 2022/23 and 2024/25; flat elsewhere
  - MAE_60+ guardrail: **PASS** (flat to slightly better)

- **Verdict:** **Reject LOSO bucket recalibration as V2A-M.** Remapping confidence alone does not reduce XI blank selections and can increase them (2024/25 16.5->21.5%, 2025/26 29.2->33.7%). The E013 overconfidence diagnosis stands, but the fix is not a post-hoc probability map - need a **structural** as-of-T minutes/availability model (who gets high base start probability), still without rates/fixtures/ILP/new-club prior. V1 remains production control.
- **Artifacts:** `records/historical/v2am_loso_summary.csv`; `engine/minutes_v2am.py`; `engine/harness_v2am.py`
- **Follow-up:** queue E015 V2A-M-v2 structural minutes (recent as-of-T minutes/starts, soften hardcoded 0.90 caps using role evidence only). Do not promote `minutes_version=v2am` to default.



### E014b - XI movement diagnostic (post-E014)
- **Date:** 2026-08-26
- **Status:** completed
- **Question:** Is E014's XI-blank regression concentrated or diffuse across buckets/roles?
- **Method:** `scripts/e014_xi_movement.py` — per GW, V1 XI (decision_decomp) vs V2A-M remap XI; tag leavers/entrants by V1 p_start bucket, position, blank outcome.
- **Results (blank rate among movers):**

  | Season | Left blank% | Entered blank% | Dominant enter bucket |
  |---|---:|---:|---|
  | 2022/23 | 22.8 | **20.9** | 0.60-0.70 (72) |
  | 2023/24 | 18.5 | **24.7** | 0.60-0.70 (82) |
  | 2024/25 | 16.9 | **30.5** | 0.60-0.70 (47) + low |
  | 2025/26 | 20.3 | **33.6** | 0.60-0.70 (67) |

- **Verdict:** **Concentrated.** Remap systematically ejects **0.80-0.90** players who mostly played, and inserts **0.60-0.70** players who blank more. 2022/23 is the exception (entered blanks ~ left blanks) — explains why XI0 was flat there while Cap rose. LOSO map is also non-monotonic (0.60-0.70 empirical > 0.70-0.80), which promotes the mid bucket into XI contention. E015 must not repeat post-hoc bucket remap; change *who earns* high base start via as-of-T recent form.
- **Artifacts:** `records/historical/e014_xi_movement.csv`

### E015 - V2A-M-v2 structural as-of-T minutes
- **Date:** 2026-08-26 (pre-registered from E014b; eval completed same day)
- **Status:** completed - **PASS** → promoted to production / V2A-M freeze (see promote note below)
- **Hypothesis:** Soft-capping season-total 0.90 claims and demoting cold recent-4 players reduces XI blanks without post-hoc remap
- **Method:** `python -m engine.harness_v2am_s` (`minutes_version=v2am_s`). Fixed rules: max base 0.85; if as_of_gw>4, cold cap 0.55 / hot floor 0.72 from last-4-GW minutes. No new-club prior. No bucket remap.
- **Seasons / GWs:** 2022/23-2025/26, GW1-38

- **Results:**

  | Season | ut_gap V1 | ut_gap V2 | XI0 V1 | XI0 V2 | XI+Cap V1 | XI+Cap V2 | MAE60 V1 | MAE60 V2 | XI0 gate |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|---|
  | 2022/23 | 0.101 | **0.046** | 27.0% | **11.5%** | 46.4 | **57.1** | 2.665 | 2.576 | PASS |
  | 2023/24 | 0.121 | **0.041** | 25.1% | **11.0%** | 44.4 | **53.7** | 2.534 | 2.482 | PASS |
  | 2024/25 | 0.113 | **0.068** | 16.5% | **10.5%** | 45.2 | **56.6** | 2.423 | 2.400 | PASS |
  | 2025/26 | 0.097 | **0.031** | 29.2% | **14.1%** | 36.3 | **50.4** | 2.662 | 2.572 | PASS |

- **Gate calls:**
  - XI 0-min hard non-inferiority: **PASS all four** (and large improvements, including the 2024/25 outlier season)
  - Upper-tail gap: **PASS** all four (model no longer claims >=0.90 by design; honesty via p>=0.75 gap)
  - XI+Cap: **PASS** all four (+7 to +14 pts/GW mean)
  - MAE_60+ guardrail: **PASS** all four (slightly better)

- **Verdict:** **E015 PASS.** Structural as-of-T recent form + soft max addresses the E014 failure mode (no mid-bucket promotion via non-monotonic remap). V2A-M = `minutes_version=v2am_s`.
- **Artifacts:** `records/historical/v2am_s_summary.csv`; `engine/minutes_struct.py`; `engine/harness_v2am_s.py`; `records/historical/e014_xi_movement.csv`
- **Follow-up:** promoted (below). E012 parallel. V2B rates next; do not retune V2A-M knobs.

### Promote — V2A-M freeze (`v2am_s`)
- **Date:** 2026-08-26
- **Status:** completed - production default flipped
- **Decision:** Explicit promote after E015 four-season PASS. Not a new experiment.
- **Code:** `project_all(..., minutes_version="v2am_s")` default. Historical control harnesses (`harness_run`, `harness_compare`, `harness_decomp`) pin `minutes_version="v1"`. Tag: `v2am-s-baseline`.
- **Frozen knobs (do not retune):** soft max 0.85; cold cap 0.55; hot floor 0.72; recent window 4 GWs post-GW4; no new-club prior; no bucket remap.
- **Invariant:** V1 (`v1.0-gw1-baseline`) remains permanent historical control. Live 2026 validates `v2am_s`; do not treat V1 GW1 as evidence for the new stack. Rates / fixtures / scoring / ILP / objective / horizon stay frozen until E016.
- **Next:** E016 V2B (rates). E012 parallel.


### E016 - V2B multi-season rate priors (pre-registered)
- **Date:** 2026-08-26 (opened after V2A-M promote; eval completed same day)
- **Status:** completed - **REJECT** (do not promote `rates_version=v2b`; production stays `rates=v1`)
- **Hypothesis:** Better per-90 rate estimates (multi-season shrinkage) improve player-level and decision-level outcomes while the entire V2A-M minutes stack stays fixed
- **Question:** Can rate improvements raise realized FPL decisions vs the earned production model (`v2am_s`), without reopening minutes / fixtures / ILP / objective / horizon?

- **Scope lock (read this first):**
  > **Multi-season rates = the player-level per-90 rate path inside `rates_for`, not fixture strength. ATK/CONCEDE/`attack_mult` remain frozen and are reserved for the later fixture experiment (V2D/B6).**

- **Axes:**

  | Axis | Control | E016 treatment |
  |---|---|---|
  | Minutes | `v2am_s` | **Locked** |
  | Player rates (`xg90`/`xa90` prior) | current `rates_for` / cost priors | **Multi-season prior** |
  | Fixtures (ATK/CONCEDE/`attack_mult`) | current | **Locked** |
  | dc / saves / bonus / cards | current | **Locked** (unchanged in E016) |
  | Scoring / ILP / objective / horizon | current | Locked |
  | MC seed | fixed | Fixed (same seed both arms) |

- **Versioning contract (orthogonal):**
  ```text
  minutes_version = "v2am_s"          # both arms
  rates_version   = "v1" | "v2b"

  control:   minutes=v2am_s + rates=v1
  treatment: minutes=v2am_s + rates=v2b
  ```
  Keep `cost_prior_xg90` / `cost_prior_xa90` available for `rates=v1`. Do not overwrite them in place; dispatch via `rates_version` (e.g. `rates_v1` / `rates_v2b`).

- **Surface (treatment variables):** **`xg90` and `xa90` only.** Do not change defensive contribution, saves, bonus, or cards in E016 unless this card is explicitly amended first.

- **As-of-T:** prior constructed only from information available before the GW being predicted (prior seasons / earlier GWs as allowed by harness). **Split historical rate evidence by club stint** — do not blindly average season-wide player rates across clubs (old-club environment is not evidence for a new-club role).

- **Historical benchmark (separate lane):** V1 (`minutes_version=v1`, `rates_version=v1`). Report as appendix; **do not** use V1 as the V2B pass/fail control.

- **Method:** `python -m engine.harness_v2b`. Fixed seed=7. Club-matched multi-season xG/xA prior (`engine/rates_v2b.py`, min 270 mins at current club); else cost prior. Four seasons individually.
- **Seasons / GWs:** 2022/23–2025/26, GW1–38
- **Results:**

  | Season | MAE60 C→T | Sp60 C→T | XI+Cap C→T | XI0 C→T | Season |
  |---|---:|---:|---:|---:|---|
  | 2022/23 | 2.576→**2.559** | 0.137→**0.144** | 57.1→**53.8** | 11.5→**12.5%** | **FAIL** Cap+XI0 |
  | 2023/24 | 2.482→**2.474** | 0.177→**0.184** | 53.7→**55.7** | 11.0→**10.8%** | PASS |
  | 2024/25 | 2.400→**2.386** | 0.161→**0.173** | 56.6→**58.2** | 10.5→**10.3%** | PASS |
  | 2025/26 | 2.572→**2.562** | 0.092→**0.097** | 50.4→**48.9** | 14.1→**15.6%** | **FAIL** Cap+XI0 |

- **Gate calls:**
  - MAE_60+ primary: **PASS all four** (small but consistent)
  - Spearman|60+: **PASS all four**
  - XI+Cap non-inferiority: **FAIL** 2022/23 and 2025/26
  - XI 0-min guardrail: **FAIL** 2022/23 and 2025/26
- **Verdict:** **REJECT** this `rates_v2b` treatment for production. Player-level rate skill improved under the frozen minutes stack, but the decision layer regressed in 2/4 seasons (XI blanks up; XI+Cap down). Instance of the **signal–selection gap** (same category as E014): better component metrics ≠ automatic better ILP selections. Do not retune minutes to compensate. Do not promote.
- **Artifacts:** `records/historical/v2b_rates_summary.csv`; `engine/rates_v2b.py`; `engine/harness_v2b.py`; `rates_version` on `project_all` (default remains `v1`)
- **Follow-up:** E016b movement diagnostic → then successor rates card if warranted. E012 parallel. Fixtures still V2D.

### E016b - XI movement diagnostic (post-E016)
- **Date:** 2026-08-26
- **Status:** completed
- **Question:** Is E016's Cap/XI0 regression concentrated or diffuse? Who enters/leaves when rates flip under frozen `v2am_s`?
- **Method:** `scripts/e016_xi_movement.py` — per GW, control XI (`rates=v1`) vs treatment XI (`rates=v2b`); tag leavers/entrants by position, p_start, `mu_delta`, `had_club_prior`, blank outcome. Seed=7 both arms.
- **Results (blank% among movers):**

  | Season | E016 gate | n swaps | left blank% | entered blank% | entered had_prior% | mean μΔ entered |
  |---|---|---:|---:|---:|---:|---:|
  | 2022/23 | FAIL | 109 | 12.8 | **16.5** | 95.4 | **+0.79** |
  | 2023/24 | PASS | 61 | 9.8 | **8.2** | 98.4 | +0.47 |
  | 2024/25 | PASS | 68 | 11.8 | **10.3** | 94.1 | +0.54 |
  | 2025/26 | FAIL | 66 | 7.6 | **16.7** | 93.9 | +0.44 |

- **Mechanism:**
  - Treatment **systematically inserts club-prior players** (entered prior% ~94–98% vs left ~58–78%) with large positive μ lifts.
  - Not an E014b-style mid-bucket remap: both arms' movers sit mostly in **0.70–0.80** p_start (minutes locked).
  - **FAIL seasons** = entered blank% > left blank% (replacements blank more than ejectees). **PASS seasons** = entered blank% ≤ left blank%.
  - 2025/26 also MID-heavy (37 MID left → 42 entered; DEF 17→11). 2022/23 has the largest swap volume (109).
- **Verdict:** **Concentrated.** `rates_v2b` preferentially promotes multi-season club-history attackers/mids via μ boost; when those replacements blank more than the players they displace, Cap/XI0 fail. PASS seasons show the same promotion pattern but with *better* replacement blank rates — so the rates axis isn't dead, but a successor must constrain **who is allowed to receive / how strongly the prior lifts μ into XI contention**, not just reblend.
- **Artifacts:** `records/historical/e016_xi_movement.csv`; `scripts/e016_xi_movement.py`
- **Follow-up:** E017 pre-registered (prior→XI promotion dampening).

### E017 - V2B prior→XI promotion dampening (pre-registered)
- **Date:** 2026-08-27 (from E016b; **not started**)
- **Status:** queued / pre-registered — **implementation contract locked** (docs only; no code yet)
- **Hypothesis:** Large club-prior–driven μ lifts are an unreliable XI promotion signal. Dampening how strongly the multi-season club prior can replace the cost prior reduces Cap/XI0 failures while preserving most of E016's MAE/Sp gains.
- **Question:** Under frozen `v2am_s`, does a **half-strength** club prior (`rates=v2b_d`) clear E016's decision gates without giving back the player-level rate improvements?

- **Evidence (E016b):** Entrants were ~94–98% club-prior with mean μΔ +0.44 to +0.79. FAIL seasons had entered blank% > left blank%; PASS seasons did not. Mechanism is **magnitude of prior-driven lift**, not identity / p_start buckets (minutes locked).

- **Scope lock:**
  > Same as E016: player-level `xg90`/`xa90` inside `rates_for` only. ATK/CONCEDE/`attack_mult` frozen (V2D). dc/saves/bonus/cards unchanged. **Dampener acts on the prior fed into blend — not a post-hoc “freeze the XI” rule.**

- **Versioning:**
  ```text
  minutes_version = "v2am_s"              # both arms
  rates_version   = "v1" | "v2b" | "v2b_d"

  control:   minutes=v2am_s + rates=v1
  treatment: minutes=v2am_s + rates=v2b_d
  ```
  `v2b` remains the rejected full club prior (appendix / ablation only). Do not use V1 minutes as pass/fail control.

- **Pinned treatment knobs (do not retune mid-run):**
  | Knob | Value | Role |
  |---|---|---|
  | `α` (club prior mix) | **0.50** | `prior = (1−α)·cost_prior + α·club_prior` for xg90 and xa90 |
  | `MIN_CLUB_MINUTES` | **270** | unchanged from E016; below this → cost prior only |
  | Surface | **xg90, xa90 only** | dc/saves/bonus/cards locked |
  | Club-stint split | **yes** | same as E016; no blind cross-club average |
  | MC seed | **7** | fixed both arms |

- **What this is not:** changing α after peeking; capping XI membership vs control; retuning V2A-M minutes; touching fixtures.

- **Method (planned):** extend `rates_version` with `v2b_d`; harness parallel to `harness_v2b` (control `v1` vs treatment `v2b_d`). Optional ablation: report `v2b` column for reference only — not a gate.
- **Seasons / GWs:** 2022/23–2025/26, GW1–38
- **Metrics / gates (same as E016; per season, not averaged):**
  1. **MAE_60+** — primary: treatment ≤ control (prefer improvement)
  2. **Spearman|60+** — non-inferiority; prefer improvement
  3. **XI+Cap** — non-inferiority every season
  4. **XI 0-min** — must not worsen vs control on any season
- **Secondary diagnostic (not a gate):** mean |μΔ| / entered blank% among XI movers vs E016b (expect smaller lifts and FAIL-season blank gap closing)
- **Cheat-blocks:** no minutes retune; no ATK/CONCEDE change; beating V1 alone ≠ pass; beating raw `v2b` alone ≠ pass; no post-hoc α search; no bundling `strategies.json`
- **Results:** —
- **Verdict:** —
- **Artifacts:** —
- **Follow-up sequence:** implement `v2b_d` → fixed-seed four-season harness → interpret → promote only if all gates PASS. E012 parallel.

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

### E012 — Evaluation-integrity property tests
- **Date:** after GW1 (not before)
- **Status:** queued
- **Hypothesis:** evaluation protocol is independent of model predictions
- **Question:** Do `evaluation_status`, `LeakFlag`, and nested regret keep their stated dependencies?
- **Method:** property tests in Python first (see `docs/FORMAL.md`). Shuffle/replace V1 predictions; recompute labels. Then optional Lean core. Not a V2 gate.
- **Seasons / GWs:** historical 2024/25 + 2025/26 tables already written
- **Metrics:** status labels identical after prediction shuffle; LeakFlag identical after V1 mutation; R_total = R_squad + R_XI + R_cap vs named oracle; shared feasible set F
- **Results:** —
- **Verdict:** —
- **Artifacts:** `docs/FORMAL.md`; tests to be added post-GW1
- **Follow-up:** Lean `formal/` only after the property tests exist. Do not block V2A-M.

---

## Current call (do not skip this when adding tests)

As of 2026-08-27 (E017 pre-registered):

1. **V2A-M FROZEN + PRODUCTION.** `minutes_version=v2am_s`. Do not retune.
2. **Rates production stays `rates=v1`.** E016 REJECT; E016b concentrated (club-prior μ promotion).
3. **E017 contract locked.** Control = `v2am_s` + `rates=v1`. Treatment = `v2am_s` + `rates=v2b_d` with **α=0.50** club/cost prior mix. Same E016 gates. Dampen prior→μ, do not freeze XI post-hoc.
4. **Next implement:** `rates_version=v2b_d` + harness → four-season eval. E012 parallel.
5. **Live 2026** validates `v2am_s` + `rates_v1`.
6. **Invariant:** minutes / fixtures / ILP / objective locked; no silent α search.

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
python -m engine.obs --season 2025-26
python -m engine.obs --season 2024-25
python -m engine.obs --season 2023-24
python -m engine.obs --season 2022-23
python scripts/e013_synthesis.py  # regenerate panel table
```
