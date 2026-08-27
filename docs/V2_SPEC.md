# V2 Research Spec

**Governing rule:** A model at version N+1 earns its place only by beating **N**
(the best earned model so far) on pre-registered out-of-sample gates.
Better-looking squads do not count. Beating an obsolete ancestor (e.g. V1 while
production is V2A-M) is an appendix, not a pass.

**Permanent historical control:** `v1.0-gw1-baseline` — never overwrite.
**Current production / active research control:** `v2am-s-baseline` (V2A-M).

---

## 0. V2A-M - Minutes / availability (**FROZEN**)

**Status:** Frozen as production default after E015 PASS (2026-08-26). Tag: `v2am-s-baseline`.
**Implementation:** `minutes_version="v2am_s"` (`engine/minutes_struct.py`).
**Permanent historical control:** V1 (`v1.0-gw1-baseline`); historical harnesses pin `minutes_version="v1"`.

**What shipped:**
- Soft max base `p_start` **0.85** (never 0.90 from season totals alone)
- After GW4: last-4-GW minutes — cold cap **0.55** / hot floor **0.72**
- No new-club prior; no bucket remap (E014 REJECT)
- Rates / fixtures / scoring / ILP / objective / horizon unchanged at freeze time

**Evidence base that justified the experiment (E013):**
- `p90_fitted` ~75-78% at model >= 0.90; XI 0-min elevated (16.5% outlier in 2024/25; ~25-29% elsewhere)
- Canonical headline: upper-tail playing-time overconfidence → XI blanks (not generic transfer mispricing / objective failure)

**E015 gate result (all four seasons PASS):** XI 0-min roughly halved; XI+Cap up; upper-tail gap improved; MAE_60+ OK.

**Do not retune these knobs.** Live 2026 validates `v2am_s` prospectively — not a retune signal.

---

## 0b. V2B - Multi-season rate priors (**REJECT** — E016)

**Status:** Implemented and evaluated 2026-08-26. **REJECT.** Production `rates_version` remains `"v1"`. See `LAB_LOG.md` E016.

**Scope lock:**
> **Multi-season rates = the player-level per-90 rate path inside `rates_for`, not fixture strength. ATK/CONCEDE/`attack_mult` remain frozen (V2D/B6).**

**What was tested:** `minutes=v2am_s` × `rates=v1` vs `rates=v2b` (club-matched multi-season xG/xA prior, min 270 mins; else cost prior). Seed fixed. dc/saves/bonus/cards unchanged.

**Result:** MAE_60+ and Spearman|60+ improved all four seasons; XI+Cap and XI 0-min **failed** on 2022/23 and 2025/26. Better rate estimates did not survive the decision layer uniformly.

**Do not promote. Do not retune minutes to compensate.**

---

## 0c. V2B-d - Prior→XI promotion dampening (**REJECT** — E017)

**Status:** Implemented and evaluated 2026-08-27. **REJECT.** Production `rates_version` remains `"v1"`. See `LAB_LOG.md` E017.

**What was tested:** `rates=v2b_d` with **α=0.50** (`prior = 0.5·cost + 0.5·club`), same club-stint / MIN_CLUB_MINUTES=270 / seed=7 stack as E016.

**Result:** MAE_60+ and Spearman|60+ improved all four seasons; XI+Cap and XI 0-min **failed** again on 2022/23 and 2025/26. Dosage diagnostics: μΔ and swap volume fell vs E016b, but FAIL seasons still had entered blank% > left blank%.

**Do not promote. Do not grid-search α.** A further rates attempt needs a **new structural card**, not a different mix weight.

---

## 0d. V2B-e - Current-form eligibility gate (**REJECT** — E018)

**Status:** Implemented and evaluated 2026-08-27. **REJECT.** Production `rates_version` remains `"v1"`. See `LAB_LOG.md` E018.

**Why:** E017b — toxic promotions = club prior on **cold/thin-form** players. E018 withheld club prior unless recent4≥90 (GW&gt;4) and season≥450.

**Result:** MAE/Sp improved all four seasons; **0/4 pass all gates.** XI0 worsened on 2023/24–2025/26; 2022/23 Cap still failed. **Club-prior branch retired** after full → damped → eligible attempts.

**Do not promote. Do not grid-search α or retune 90/450.** Pivot to V2C/V2D as parallel branches.

**E018s (2026-08-27):** Family synthesis → **B**. Club-history contains predictive information but μ perturbations are not reliably safe for the current ILP. Retirement is of this packaging, not of all historical-rate research.

---

## 0f. V2C-e - Cold-eligible competition demotion (**REJECT** — E020)

**Status:** Implemented and evaluated 2026-08-27. **REJECT.** Production stays `v2am_s`. See `LAB_LOG.md` E020.

**What changed vs E019:** same demotion rungs; skip demotion when `recent4 ≥ 90` (was ≥270).

**Result:** XI0 PASS 4/4; Cap PASS 3/4 (only 2022/23 fails — improved vs E019); MAE_60+ FAIL 4/4. Do not promote. Do not retune 90/rungs.

---

## 0g. V2D - Learned fixture coefficients (**REJECT** — E021)

**Status:** Implemented + evaluated 2026-08-27. **REJECT.** See `LAB_LOG.md` E021.

**Control:** `minutes=v2am_s` + `rates=v1` + `fixtures=v1` (hand `ATK`/`CONCEDE`)  
**Treatment:** same minutes/rates + `fixtures=v2d` (prior-season empirical team attack/defence)

**Pinned:**
- Fit from **complete prior seasons only** (team name keys); promoted clubs → league-average attack/defence
- Home/away multipliers **1.10 / 0.88** frozen; `LEAGUE_AVG` / clamp frozen
- Dispatch `fixtures_version`; default stays `"v1"`
- Gates: XI0 + Cap hard vs control; MAE_60+ guardrail; four seasons; seed=7

**Result:** MAE_60+ PASS 4/4; Cap FAIL 4/4; XI0 FAIL 4/4 (~180 swaps/season). Do not promote. Do not retune multipliers. Production fixtures stay `v1`.

**E021b:** Fixture XI movers match rates toxicology — entered blank% > left every season; prior_str+recent4&lt;90 blank **61%**.

**E021c:** That 61% is **true zeros**. Cold 60+ (n=20) outscore treat μ on average. Packaging should target minutes-reliability of increments into decision U.

**Not:** multiplier search; same-GW leakage fits; minutes/rates retune; ML fixture models; E018-style `if cold: zero signal` disguised as packaging.

---

## 0h. Packaging - Decision-safe fixture μΔ (**E022 PASS**; **E023 REJECT for promote**)

**E022:** PASS vs raw v2d. Mechanism validated. Not promoted. See `LAB_LOG.md` E022.

**E023:** Packaged v2d vs production fixtures=v1 — MAE✓; Cap mostly✓; **XI0✗ 4/4** (named risk). Reject promote. No q fishing. See `LAB_LOG.md` E023.

**Not:** q fishing; silent promote; V2C/rates reopen.

---

## 1. Harness requirements

The harness is the prerequisite for B4–B7. Getting it wrong produces silent
lookahead bias — a wrong number that looks rigorous is more dangerous than no
number at all.

### 1.1 As-of-T discipline

`api.py` currently caches with a wall-clock TTL. The backtester needs a different
cache key:

```
(season, gameweek, snapshot_type)
```

Concrete directory layout:

```
.cache/fpl/
  2025-26/
    gw01/
      bootstrap.json    <- written once, never overwritten
      fixtures.json
      meta.json         <- {"as_of": "<ISO>", "deadline": "<ISO>"}
    gw02/
    ...
  2026-27/
    gw01/              <- the live V1 snapshot
```

Rules:

- **Write-once per key.** If the file exists, `load_historical_snapshot(season, gw)`
  returns it and never calls the API again for that slot.
- **Read-only during evaluation.** The projection engine reads the snapshot; it
  never touches the network during a backtest.
- **Deadline-gated.** Any feature at GW n must come from a snapshot with
  `as_of < deadline_n`. Reject the snapshot if that condition is violated.

Function signature to add to `api.py`:

```python
def load_historical_snapshot(season: str, gw: int) -> Snapshot:
    """Load a frozen pre-deadline snapshot. Raises FileNotFoundError if not scraped."""
```

### 1.2 What Vaastav actually gives you

`gws/merged_gw.csv` gives per-player, per-GW actuals. That is the **ground truth**
for scoring projections.

It does **not** give you the pre-deadline snapshot state — player prices, `ep_this`
values, injury flags as they existed at each deadline. Since Vaastav switched to
three season dumps from 2025/26 onward, GW-by-GW pre-deadline inputs are not
reliably available.

**Practical approximation for V2:** use Vaastav actuals as the target, and treat
pre-deadline inputs as bootstrap-at-season-start plus the GW-by-GW stats up to
GW n−1. Document this approximation explicitly in every results table.

### 1.3 Capture schema

For each (season, GW, player), one row:

```
prediction_as_of | season | gw | player_id | model_version
predicted_mu | predicted_sigma | predicted_p_start | predicted_p_60 | predicted_p_10
actual_points | actual_minutes | actual_started
```

Summary metrics per model version and GW:

| Metric | What it measures |
|---|---|
| MAE on predicted_mu vs actual_points | Point estimate accuracy |
| RMSE | Penalises large misses |
| Spearman rank correlation | Ranking accuracy — most important for the ILP |
| p_start calibration | Is P(start)=0.90 actually 90% across the sample? |
| Decision quality | Did the ILP on this model earn more realized XI points? |

---

## 2. B0–B7 model ladder

### B0 — FPL ep_next through the ILP

Already run (GW1 2026/27): 5/15 overlap with V1. GW1-only question, not a
6-GW horizon model. Shared core with V1: essentially Fernandes + Gabriel.

### B1 — Last-season total_points through the ILP

Already run: 3/15 overlap. Backward-looking, no fixture or minutes adjustment.

### B2 — Naive points/90 (minutes >= 900) through the ILP

Already run: 2/15 overlap. Floors tiny samples; still attacker-biased.

### B3 — V1 (permanent historical baseline)

Permanent historical control (`v1.0-gw1-baseline`). Still reported as a benchmark
lane. **Not** the active pass/fail control for V2B+ — that is V2A-M (`v2am_s`).

Confirmed finding: Haaland's exclusion from the balanced ILP is not a V1
fixture-model artifact. Official ep_next through the same ILP also excludes him.
It is a portfolio-allocation decision at £15.5m. Forcing him in costs 4.86
objective points and swaps out Fernandes + Saka + structure, not just cheap
forwards.

### B4 — V2B multi-season shrinkage prior (E016)

See §0b for the locked contract. Summary:

**Control:** `minutes=v2am_s` + `rates=v1` (cost-prior blend).  
**Treatment:** `minutes=v2am_s` + `rates=v2b` (multi-season xG/xA prior).

**What changes:** `xg90` / `xa90` priors inside `rates_for` only — minutes-weighted
blend of prior-season per-90 rates (club-stint split). Preserve cost priors for
`rates=v1`; dispatch by `rates_version`.

**What does not change:** V2A-M minutes knobs, ATK, CONCEDE, `attack_mult`,
dc/saves/bonus/cards, BENCH_WEIGHT, optimizer, objective, horizon, MC seed protocol.

**Validation target:** beat V2A-M control on E016 gates on all four seasons.
V1 comparison is appendix only.

**Key risk:** blind season-wide averages across club changes. Split by club stint.

### B5 — V2C role-transition minutes (E019) — **REJECT**

See §0e. Competition demotion improved XI0 but failed Cap/MAE gates. Production stays `v2am_s`.

### B6 — V1 + B4 + B5

Stacked improvements. Only build if B4 and B5 each individually beat B3.
If only one improves on B3, use only that one.

### B7 — V2D learned fixture coefficients (E021) — **REJECT**

See §0g / `LAB_LOG.md` E021. MAE_60+ improved; Cap/XI0 failed 4/4. Production fixtures stay `v1`. No multiplier fishing.

Older “after B5” ordering is obsolete; V2D was an independent parallel branch.

### B8 — Packaging decision utility for fixture μΔ (E022) — **PASS vs raw v2d**

See §0h / `LAB_LOG.md` E022. Cap+XI0 PASS 4/4; not a production promote.

### B9 — Packaged v2d vs production fixtures=v1 (E023) — **REJECT for promote**

See §0h / `LAB_LOG.md` E023. XI0✗ 4/4 as named risk. Packaging mechanism (E022) remains validated; production fixtures stay `v1`. No q fishing.

---

## 3. After GW1: prediction capture

Before looking at results, run:

```bash
python -m engine.capture --gw 1
```

This script should:

1. Read frozen V1 projections from `.cache/fpl/2026-27/gw01/`
2. Fetch GW1 actuals (FPL live-elements API or Vaastav once available)
3. Write `records/gw01_v1.0.csv` using the capture schema above
4. Print: MAE, RMSE, Spearman, p_start calibration

Do not inspect the actuals before the capture file is written.

---

## 4. Out of scope for this spec

The following are real improvements deferred until after the B0–B7 ladder is
measured:

| Feature | Reason deferred |
|---|---|
| Chip timing (Bench Boost, Triple Captain, Free Hit) | Separate decision layer; not a projection problem |
| Transfer optimization lookahead | Requires current squad state; separate ILP formulation |
| Rank / ownership strategy | Depends on in-season rank and league context |
| Captain-doubling in the squad ILP | Changes the objective structure; post-B7 |
| ML models (XGBoost, neural nets, ensemble) | Only after B7 is measured; no model earns a position without beating the prior rung |

---

## 5. Known V1 limitations (reference for backtest scoring)

| Limitation | Location | Audit evidence | Fix in |
|---|---|---|---|
| New-club minutes inherited from old club | minutes.py build_role_start | Guehi Delta = 1.94, third-largest squad driver | B5 |
| Attack/defence splits zero pre-season | fixtures.py ATK/CONCEDE | Coarse fixture xG for elite-vs-weak matchups | B7 |
| No captain-doubling in squad objective | optimize.py objective | 4.86 lock cost for Haaland is a lower bound | Post-B7 |
| Single-season per-90 as projection base | project.py rates_for | Small-sample noise for transfers / new signings | B4 |
| No multi-GW XI selection in squad solve | optimize.py | Horizon squad implicitly built around one latent XI | Post-B7 |

---

## 6. Scientific discipline

- V1.0 is the permanent control. Do not modify it retroactively.
- Every experiment version gets a git tag: `v1.1-b4-shrinkage`, `v1.2-b5-minutes`, etc.
- A model that beats V1 on squad appearance but not on out-of-sample metrics is discarded.
- The harness must be validated on historical seasons before being trusted on live 2026/27 data.
- As-of-T discipline is non-negotiable: a feature using post-deadline information voids the experiment.
- Formal integrity (`docs/FORMAL.md`) is not a V2 gate. V2 earns its place empirically. Lean / property tests start after GW1 (E012) and check that the compare still measures the same question.
