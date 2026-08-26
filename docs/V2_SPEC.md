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

## 0b. V2B - Multi-season rate priors (**OPEN** — E016)

**Status:** Pre-registered 2026-08-26. Not implemented. See `LAB_LOG.md` E016.

**Control:** V2A-M (`v2am_s`) + current rates + current fixtures/scoring/ILP/objective/horizon.  
**Treatment:** same stack + multi-season rate improvement only (`rates_for` / prior path).  
**Not the control:** V1. Report V1 as a separate historical benchmark only.

**Gates (per season):** MAE_60+ (primary); Spearman among mins≥60; XI+Cap non-inferiority; XI 0-min guardrail (must not worsen vs V2A-M).  
**Locked:** V2A-M minutes knobs, fixtures, scoring, ILP, objective, horizon.

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

**Control:** V2A-M (`v2am_s`) + current `rates_for` cost-prior blend.  
**Treatment:** same + multi-season rate prior only.

**What changes:** `cost_prior_xg90` / `cost_prior_xa90` / `rates_for` path in
`project.py` — minutes-weighted blend of prior seasons' per-90 rates. Players with
large current-season minutes receive near-zero shrinkage; thin samples receive
fuller shrinkage toward the multi-season average.

**What does not change:** V2A-M minutes knobs, ATK, CONCEDE, BENCH_WEIGHT,
optimizer, objective, horizon.

**Validation target:** beat V2A-M control on E016 gates (MAE_60+, Spearman|60+,
XI+Cap non-inferiority, XI 0-min guardrail) on all four seasons. V1 comparison
is appendix only.

**Key risk:** season-average per-90 stats for mid-season transfers are misleading.
Split by club-stint before averaging, or treat mid-season transfers separately.

### B5 — V1 + role-transition minutes model

Highest-value experiment, identified directly by the GW1 audit.

Audit finding: Guehi, Delta = 1.94 (third-largest leave-one-out driver), with
Palace 2025/26 minutes mapped as a 0.90 Man City start probability. This is the
specific structural bug B5 fixes.

**What changes:** `build_role_start` in `minutes.py`. Replace the single
`_outfield_start` curve with three cases:

1. **Returning starters** — same club, >= 1800 mins last season, no material
   competition added. Current curve, high confidence.
2. **New-club players** — current team_id differs from the club where they
   accumulated most of last season's minutes (detected via Vaastav per-GW history).
   Prior discounted by new-club positional depth: count how many other players at
   that position in the new club have >= 1800 mins. More competition -> lower prior.
3. **Promoted-club players** — separate curve calibrated on past seasons of newly-
   promoted sides.

**What does not change:** fixture model, ATK, CONCEDE, projection coefficients,
optimizer.

**Validation target:** better-calibrated p_start specifically for new-club players,
measured against the last 3 seasons of summer and January transfer windows.

### B6 — V1 + B4 + B5

Stacked improvements. Only build if B4 and B5 each individually beat B3.
If only one improves on B3, use only that one.

### B7 — V1 + B6 + learned fixture coefficients

**What changes:** ATK / CONCEDE in `fixtures.py` fitted from historical Premier
League match results using a Poisson GLM (Dixon-Coles or similar). Attack and
defence strength per team estimated from actual goal outcomes, not the FPL 1–5
strength scale.

**Key constraint:** at season start the FPL attack/defence splits are zero. B7
at GW1 still falls back to a fitted mapping from overall strength to xG. It can
update on actual 2026/27 results from GW3–4 onward.

**When to build:** last, and only after B5 is measured and validated. Fixture
uncertainty is fundamental at season start — diminishing returns kick in early.

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
