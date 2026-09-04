# Project methods

This file explains **what was done to the data**: sources, freezes, the projection
and optimiser, every statistical and mathematical method that actually exists in
the code, the hypothesis board, the gates, and the experiment map.

It does **not** replace the living experiment log. Numbers and verdicts live in
[`LAB_LOG.md`](LAB_LOG.md). If a table here disagrees with that log, the log wins.

---

## 1. Reading order

| Document | Job |
|---|---|
| **This file** | Methods, math, provenance, how to read a result |
| [`LAB_LOG.md`](LAB_LOG.md) | Hypotheses, E001–E013, tables, verdicts (append-only) |
| [`HARNESS_SPEC.md`](HARNESS_SPEC.md) | As-of-T reconstruction rules and pass/fail gates |
| [`V2_INVESTIGATION.md`](V2_INVESTIGATION.md) | Nested regret, evaluation status, H0–H3 protocol |
| [`V2_SPEC.md`](V2_SPEC.md) | How a successor model earns a version number |
| [`FORMAL.md`](FORMAL.md) | What Lean could prove vs what statistics prove (post-GW1) |
| [`DECISION_ARCHITECTURE.md`](DECISION_ARCHITECTURE.md) | Decision-layer history, failure modes, E030–E036 |
| [`DECISION_CHARTER.md`](DECISION_CHARTER.md) | Landing A; rates_v2b closed; Research / Upstream / Product fork |
| [`PORTFOLIO_VALUE_SPEC.md`](PORTFOLIO_VALUE_SPEC.md) | Candidate \(V(S)\), E035–E037 results |
| `ROADMAP.md` | Version ladder (may lag E013; do not treat it as the experiment log) |

Python tells us what happened. Statistics tell us whether it is reproducible.
Formal integrity (queued as E012) would tell us whether we accidentally changed
the question while measuring it [`FORMAL.md`](FORMAL.md).

---

## 2. What the system is

FPL V1 is a **projection-first** Fantasy Premier League squad picker for 2026/27.

```text
official FPL API / Vaastav historical files
        ↓
   Snapshot (as-of-T)
        ↓
   engine/project.py     μ, σ, p_start, P(10+) per player-GW
        ↓
   engine/optimize.py    legal 15, then XI, then captain
        ↓
   records/*.csv         frozen artefacts
        ↓
   export_ui.py          JSON for the viewer
        ↓
   web/                  read-only display
```

The projection engine is the brain. The integer linear program (ILP) is the
decision layer. The web UI is a **viewer of frozen artefacts**, not a second
place the Friday squad is chosen. A live-season strategy board exists as a
documented re-solve of the same ILP against the cached snapshot
(`scripts/export_strategies.py`); it is not a `capture.py` record.

---

## 3. Data sources and provenance

### 3.1 Official FPL API

Live 2026/27 snapshots come from the public Fantasy Premier League API
[1]: `bootstrap-static`, `fixtures`, `event/{gw}/live`, and public `entry`
endpoints. The engine caches them under `.cache/fpl/`. Opening prices, status,
news, `chance_of_playing_next_round`, and team strength are snapshot fields.
They are **not** the same object as the frozen prediction record.

### 3.2 Vaastav historical dataset

Historical actuals, per-GW player rows, fixtures, team lists, and official `xP`
come from Vaastav Anasane's Fantasy Premier League dataset [2], cloned on first
use into `data/vaastav/`. Identity across seasons uses Vaastav `code`, not the
season-local FPL `element` id.

Vaastav themselves document that `xP` can include post-deadline information.
That is why historical snapshots **exclude** `ep_next` / official xP from the
predictor, and why E008 tests Spearman(`xP`, actual) as an evaluation-time
leakage flag rather than treating B0 as a fair baseline
[`HARNESS_SPEC.md`](HARNESS_SPEC.md).

Season-end `players_raw.csv` is never used as a GW1 snapshot: end-of-season
`now_cost`, `minutes`, and `total_points` contain future information. Opening
prices come from `gws/gw{N}.csv` `value`.

### 3.3 What a prediction at time T may see

| Input | Allowed at prediction time |
|---|---|
| Player identity / team | Yes |
| Opening price for GW N | Yes |
| Prior-season per-90 rates (by `code`) | Yes |
| Current-season stats | Only through GW N−1 |
| Team strength (season-start) | Yes |
| Fixtures for GW N (unfinished) | Yes |
| `ep_next` / official xP | **No** (historical) |
| Untimestamped news / `chance_this` | **No** (historical) |
| GW N actual points | Scoring only |

Two different claims, both required:

- **Provenance** (this harness): the column was built from sources allowed at T.
- **Type-level cutoff** ([`FORMAL.md`](FORMAL.md), post-GW1): a predictor of
  snapshot T has no parameter for actuals at T or later.

A well-typed snapshot can still contain contaminated `xP`. A reconstructed
snapshot can still be passed to a function that also reads future files.

`LeakFlag` is evaluation-time. It may see actuals. Prediction may not.

---

## 4. Versions, tags, freezes

**Tag:** `v1.0-gw1-baseline` — frozen before the 2026/27 GW1 deadline
(2026-08-21 17:30 UTC). Never overwrite it. It is the permanent control.

Two freezes were pre-registered on 2026-08-18, before E008/E009:

| Freeze | May change before deadline? | Generates |
|---|---|---|
| **Production** | No | Friday team: V1.0 projection, minutes, fixtures, coefficients, optimiser, objective |
| **Research calendar** | Beliefs only | Historical lab, V2 priorities, post-GW1 plan |

Research can change our beliefs before GW1. It cannot change the frozen
experiment.

**Friday default 15** (timestamped before E008/E009): V1 balanced solve from the
freeze snapshot (`engine.audit` 2026-08-18 09:17 UTC / `records/gw01_v1.0.csv`).
Guehi IN, Haaland OUT, no human overlay. Ugly E009 is V2 evidence; it does not
exclude Guehi on Thursday.

A successor model at version N+1 earns its place only by beating N on
out-of-sample MAE / Spearman on realised GW points. Better-looking squads do
not count [`V2_SPEC.md`](V2_SPEC.md).

**Research ladder after GW1** (from the E013 call, not the older Guehi-centric
framing): V2A-M (minutes/availability) → V2B (multi-season rate priors) → V2C
(role-transition / transfer-specific effects) → V2D (learned fixture
coefficients). Each rung beats the preceding control out-of-sample before it is
retained.

---

## 5. Pipeline

```text
Snapshot
  → rates_for (blend observed xG/xA with a cost prior)
  → minutes_probs (p_start, p_sub, p_60) × availability
  → project_player_gw: 2500 Monte Carlo draws of FPL scoring events
  → μ = mean, σ = sample std, P(10+) = fraction of sims with ≥ 10 points
  → strategy utility u(μ, σ, P(10+))
  → horizon: U = Σ_k 0.90^k u(GW_{t+k}), production k = 0..5
  → solve_squad (15 + starting XI) then pick_captains
```

Live freeze: `python -m engine.capture --gw 1` writes `records/gw01_v1.0.csv`
(balanced, player-GW projections). Historical freeze: `engine.harness_run`
writes the same schema under `records/historical/{season}/`.

Scoring after actuals land uses `engine/metrics.py` for both tracks.

---

## 6. Methods encyclopedia

Only methods that exist in this repository. Cost-prior xG/xA is a **local
heuristic**, not a published expected-goals model. We do not implement
Dixon–Coles, bivariate Poisson match models, or a parametric Normal points
distribution.

### 6.1 Minutes mixture

**Where:** [`engine/minutes.py`](../engine/minutes.py).

**What it is.** Playing time is not a single number. V1 models three
probabilities for each player and horizon slot: start, come on as a substitute,
and play 60+ minutes (needed for clean-sheet eligibility).

**How.** `availability` maps FPL status (`a`, `d`, `i`, `s`, `u`, `n`) and
`chance_of_playing_*` into a 0–1 multiplier that can recover over later
horizon slots. `build_role_start` ranks players within each club and position;
**only one goalkeeper per club** is treated as the starter, because last-season
minutes would otherwise make every backup who started elsewhere look nailed
(H-audit-gk). Outfield `p_start` is a step function of last-season minutes,
starts, and price, then multiplied by availability and capped at 0.97.
`p_60 ≈ 0.93 p_start + 0.08 p_sub`.

**How we used it.** These probabilities mix three simulated roles (start / sub /
blank) inside `project_player_gw`. E009/E013 then compared claimed `p_start`
with observed starts. Upper-tail overconfidence is V1's repeatable weakness.

### 6.2 Rate blending

**Where:** `blend`, `cost_prior_xg90`, `cost_prior_xa90`, `rates_for` in
[`engine/project.py`](../engine/project.py).

**What it is.** Per-90 attacking rates shrink toward a price-and-position prior
when the player has few minutes:

```text
w = min(1, minutes / 1800)
rate = w · observed + (1 − w) · prior(position, price)
```

Defensive contribution uses a shorter 900-minute blend. Penalty-taker and
corner-taker bumps apply when minutes < 450.

This is **not** a published xG model. It is a shrinkage heuristic so that a
£4.5m player with 20 minutes does not inherit a noisy 2.0 xG/90.

**Event model (conditional on minutes).** Goals, assists, and saves are drawn
as Poisson with λ scaled by `mins/90`. Clean sheets and defensive-contribution
flags are Bernoulli. Goals conceded use FPL's −1 per two goals bucket for
GKP/DEF. Yellows and bonus are also simulated. Points use the live scoring
rules in [`engine/scoring.py`](../engine/scoring.py) (appearance 1/2,
position-dependent goals, CS, DC, etc.).

### 6.3 Monte Carlo projection

**Where:** `project_player_gw`, `N_SIMS = 2500` in
[`engine/project.py`](../engine/project.py).

**What it is.** For each player-GW, 2500 independent draws of the minutes
mixture and the event model produce a sample of FPL points. Then:

```text
μ      = mean(points)
σ      = std(points)          (sample standard deviation of the sims)
P(10+) = (# of sims with points ≥ 10) / 2500
```

The sample is **not** assumed Gaussian. FPL points are lumpy (0, 2, 6, 10, 13…).
Drawing a bell curve from μ and σ alone would assert a shape the simulation
never produced. The UI therefore leaves the outcome-distribution panel empty
until sim quantiles are persisted (Audit surface / Phase 6).

Seed: `project_all` uses a fixed RNG seed (7) so a freeze is reproducible given
the same snapshot.

### 6.4 Horizon utility and strategies

**Where:** `DECAY = 0.90`, `utility`, `project_all` in
[`engine/project.py`](../engine/project.py).

Production V1 solves a **six-gameweek** objective. Later weeks are discounted:

```text
U = Σ_{k=0}^{5}  0.90^k  u(μ_k, σ_k, P(10+)_k)
```

Strategy changes `u`, not the constraint set:

| Strategy | u |
|---|---|
| safe | μ − 0.40 σ |
| balanced | μ |
| aggressive | μ + 3 P(10+) |

`next_utility` is the k=0 term only. The E007 `V1_GW1` counterfactual keeps the
same μ and solves the ILP on `next_utility` instead of `U`. A large lift would
mean the evaluation scoreboard and the 6-GW squad objective differ; it is not
a deploy decision. E013 found **inconsistent sign** across four seasons
(including −0.48 pts/GW on 2022/23 CLEAN), so H2 is weak.

Historical compare records (E006) used **horizon=1** so ILP utility ≈ next-GW μ.
Do not mix those XI+Cap means with the horizon-6 decomp (E007) without naming
the difference.

### 6.5 Integer linear program (squad and XI)

**Where:** [`engine/optimize.py`](../engine/optimize.py). Solver: PuLP with
COIN-OR CBC [5][6].

**What it is.** An ILP is a linear objective over 0–1 (or integer) variables
with linear constraints. Here:

- `x_i = 1` if player i is in the 15.
- `s_i = 1` if player i starts (implies `s_i ≤ x_i`).

Objective (effective playing utility):

```text
max  Σ_i  util_i · (0.12 x_i + 0.88 s_i)
```

`BENCH_WEIGHT = 0.12` so the bench is not worth the same as the XI. Equal
15-man sums were how Haaland lost to three mid-price forwards (H-audit-bench).

Constraints (from the live `SquadRules` snapshot): 15 players; 11 starters;
budget ≤ £100m (stored as tenths); squad counts 2 GKP / 5 DEF / 5 MID / 3 FWD;
XI formation bounds; ≤ 3 players per club. `must_include` / `must_exclude`
locks are optional (Haaland experiment).

A second ILP, `solve_xi`, picks 11 from a fixed 15 using **next-GW** utility.
Captain is the XI player with highest `next_utility`; vice maximises
`p_start · next_μ` among the rest.

**How we used it.** Live GW1 audit (E001), historical XI+Cap (E006/E007), and
the UI strategy toggle (re-solve only; not a frozen record).

### 6.6 MAE, RMSE, bias

**Where:** [`engine/metrics.py`](../engine/metrics.py). Target: `actual_points`
vs predicted `μ` on player-GW rows with both present.

```text
MAE  = mean |μ − y|
RMSE = sqrt(mean (μ − y)²)
bias = mean (μ − y)
```

MAE is the typical absolute miss in FPL points. RMSE penalises large misses.
Positive bias means over-prediction. E004 GW1: MAE 1.44 / 1.26, Spearman ~0.37,
slight positive bias. Late-season MAE drop (E005) is expected because the
snapshot accumulates current-season minutes; it is **not** evidence that
preseason V1 is strong.

**Conditional MAE (E009).** MAE among players with ≥ 60 minutes is *higher*
than among those with < 60 (real point variance among those who play). That
does not mean “fix xG first.” The decision-level miss is XI slots that play
zero minutes.

### 6.7 Spearman rank correlation

**Where:** `spearman` in [`engine/metrics.py`](../engine/metrics.py).

**What it is.** Spearman's ρ [3] is Pearson correlation of **ranks**. If μ ranks
players the same way actual points do, ρ is high even if the point totals are
wrong. That is the ranking skill the ILP cares about.

Implementation: assign ranks 1…n by sorting (ties are not averaged; a known
simplification), then

```text
ρ =  Σ (r_x − r̄_x)(r_y − r̄_y)
    ─────────────────────────────────────────
    sqrt( Σ (r_x − r̄_x)²  ·  Σ (r_y − r̄_y)² )
```

**How we used it.**

- Player-level skill of V1 μ vs actuals (E004–E006).
- **E008 leakage flag (pre-registered before the query):** flag a gameweek if
  Spearman(Vaastav `xP`, actual points) > 0.70, computed from xP vs actual
  **only**, never from V1 scores. Flagged: 10/38 (2025/26), 34/38 (2024/25),
  33/38 (2022/23), 31/38 (2023/24) per E013.

B0 on a flagged week is an upper-bound diagnostic, not a V2 gate.

### 6.8 Expected calibration error (ECE)

**Where:** `calibration_error` in [`engine/metrics.py`](../engine/metrics.py).

**What it is.** A proper scoring rule for probabilities asks whether a claimed
p matches the observed frequency. ECE [4] is a weighted average of
|claimed − observed| over bins:

```text
ECE = Σ_b  (n_b / n)  | mean(p in bin b) − mean(outcome in bin b) |
```

This implementation uses **five equal-width bins** on p ∈ [0, 1]
(`b = min(int(p · 5), 4)`). Outcomes: `did_start` (minutes ≥ 45 in capture;
a proxy because the FPL API does not expose started-or-not) for `p_start`,
and 1{actual ≥ 10} for P(10+).

**How we used it.** E004 reports p_start ECE 0.095 / 0.127 and small p10 ECE.
Pooled ECE is **not** a V2 cheat-block. A model could look calibrated on
average and still overclaim the 0.90+ tail that fills the XI. V2A-M therefore
leads with `p90_fitted` and XI 0-min, not ECE alone [`V2_SPEC.md`](V2_SPEC.md).

### 6.9 p90_fitted and the bucket table

**Where:** `engine/obs.py` / `minutes_cal_fit.csv`; synthesis in E013.

**What it is.** Among player-GWs with claimed `p_start ≥ 0.90`, what fraction
actually started? A logistic curve is also fit on `p_start ≥ 0.60` for a
diagnostic appendix (`alpha`, `beta`, `P@0.90 fit`).

E013: **p90_fitted ≈ 75–78%** on all four seasons (fitted 77.2, 75.0, 75.6,
77.6). Raw start% in the 0.90–1.00 bucket is similar (79–84%). Logistic β ≪ 1
everywhere (nonlinear tail compression). α/β **trade off and sign-flip** across
splits; they must not inform design. Prefer bucket recalibration over a single
multiplicative shrink.

### 6.10 Nested hindsight regret

**Where:** [`docs/V2_INVESTIGATION.md`](V2_INVESTIGATION.md);
`engine/harness_decomp.py`; `decision_gw.csv`.

**What it is.** After the gameweek, a god-mode oracle knows every player's
actual points and can pick a legal 15, XI, and captain. Nested regret splits
the gap from that oracle to V1's realised lineup:

```text
R_squad = P(oracle 15+XI+cap) − P(best XI+cap from V1's 15)
R_XI    = P(best XI+cap from V1's 15) − P(V1 XI + best captain)
R_cap   = P(V1 XI + best captain) − P(V1 XI + V1 captain)
R_total = R_squad + R_XI + R_cap
        = P(oracle) − P(V1 realised)
```

This is **not** the B0 gap. E007's “86% squad” share is vs the hindsight 15,
not “the optimiser is why B0 wins.” Never collapse the two.

**Evaluation status** is set from structure only (`clean` / `flagged` /
`excluded`): fixture count, missing actuals, join failure — never from
`V1 XI+Cap < 15` or `B0 XI+Cap > 80`. Those are inspection flags only.
Circular-exclusion: shuffling V1 predictions must not flip `evaluation_status`
(E012, queued).

### 6.11 Baselines B0–B3

| ID | Source | Role |
|---|---|---|
| B0 | Vaastav / official `xP` | Contaminated on many GWs (E008). Upper bound, never a V2 gate |
| B1 | Last-season total points | Naive; V1 beats it on XI+Cap all four seasons |
| B2 | Prior-season points/90 (minutes ≥ 900) | Naive; V1 beats it on XI+Cap all four seasons |
| B3 | V1 on the as-of-T snapshot | Control |

XI+Cap scores **actual FPL points** of the ILP eleven with captain doubled.

---

## 7. Hypotheses and gates

Status as of 2026-08-26 (V2A-M frozen = `v2am_s`; V1 permanent historical control). Full board:
[`LAB_LOG.md`](LAB_LOG.md#hypothesis-board).

| ID | Claim | Status |
|---|---|---|
| H-audit-gk | Backup GKs inherit starter minutes from old clubs | supported (qualitative) |
| H-audit-bench | Equal 15-man sum undervalues premiums | supported (qualitative) |
| H-audit-guehi | New-club minutes/role is a large LOO driver | supported (qualitative) |
| H-audit-haaland | Forcing Haaland costs ~5 objective vs diversified 15 | supported (V1 objective) |
| H0 | Leaky B0 / anomalous weeks dominate decision *means* | **supported** |
| H0a | Vaastav xP has post-deadline / near-oracle information on some GWs | **supported** |
| H0b | V1 missing legitimate pre-deadline minutes/availability (XI layer) | **supported** |
| H1 | Rate error (xG/xA/fixture) is the main clean-week problem | **not first lever** |
| H2 | 6-GW objective vs GW-N scoreboard explains the B0 gap | **weak** |
| H3 | Small μ errors × ILP × budget cause large XI jumps | open |
| H-v1-naive | V1 beats B1 and B2 at decision level | **supported** |
| H-v1-xp | V1 beats B0 at MAE and XI+Cap | **not supported as stated** |

### Harness validation gates (must pass before historical evidence)

From [`HARNESS_SPEC.md`](HARNESS_SPEC.md): player count ≥ 500; `ep_next` is
None for all players; current-season minutes/points are 0 at GW1 (or match
the sum through GW N−1 when rolling); prices match GW opening `value`; target
fixtures exist and are unfinished; `next_event` equals the target GW.

### E008 leakage gate (pre-registered)

Spearman(`xP`, actual) > 0.70, from xP vs actual only. Sets `LeakFlag`. Must
not be computed from V1 scores.

### V2A-M gates (completed — E015 PASS; frozen as `v2am_s`)

Historical control for that experiment was V1. Treatment: revised minutes only.
E015 passed all four seasons; production default is now `v2am_s`. Do not retune.

Canonical statement (E013): V1's repeatable weakness was **upper-tail
playing-time overconfidence propagating into XI blank selections**.

### V2B gates (E016/E017/E018 REJECT — family retired; E018s = B)

Three structural club-prior treatments improved MAE/Sp but never cleared decision gates. E018s: **B** — signal useful, unsafe under current ILP. Production `rates_version=v1`. Club-prior family closed.

### V2C gates (E019/E020 REJECT; E019b concentrated)

E019: XI0✓ Cap✗2 MAE✗4. E019b: false-positive demotion. E020 cold-eligible: Cap✗ only 2022/23; MAE✗4. Production `v2am_s`. No further recent4-threshold fishing.

### V2D gates (E021 REJECT; E021b concentrated; E021c mostly non-playing)

MAE_60+ ✓ 4/4; Cap✗ XI0✗ 4/4. E021b: cold prior_str blank 61%. E021c: that blank rate is **true zeros**; cold 60+ (n=20) outscore treat μ. Production fixtures `v1`.

### Packaging gates (CLOSED after E024b)

E022 PASS vs raw; E023/E024 REJECT vs production. E024b: Cap = wrong-player-when-playing (`q≈1`; blanks similar FAIL/PASS).
**Reach:** availability risk only — not valuation among reliable players. Do not enlarge q. Do not promote. Production unchanged.

### Valuation / selection (E038 concentrated; Phase 0 freeze)

E038: both rolling and GW1-lock season ΣΔCap negative on FAIL — Landing A (season-structural).
**`rates_v2b` promote CLOSED** — reopen requires new prereg. Post-E038 roadmap forks
Research / Upstream / Product (one implement lane). Charter: `docs/DECISION_CHARTER.md`.
Production unchanged: `v2am_s` + `rates=v1` + fixtures `v1`.

---

## 8. Experiment map

Details and tables: [`LAB_LOG.md`](LAB_LOG.md). One line each.

| ID | Question | Verdict |
|---|---|---|
| **E001** | Is the frozen V1 15 legal, and what drives it? | Legal £100m 15; C Fernandes; Haaland lock Δ = −4.86; Guehi LOO 1.94 |
| **E002** | Freeze GW1 μ/σ/p_start before kickoff | 590 rows → `records/gw01_v1.0.csv` |
| **E003** | Does as-of-T GW1 reconstruction leak? | PASS 2024/25 and 2025/26 (later 2022–23 / 2023–24 in E013) |
| **E004** | Preseason GW1 μ vs actuals | Weak positive Spearman (~0.37); slight over-prediction |
| **E005** | Rolling GW1–38 freeze+score | 38/38 written; late-season Spearman rise is expected, not preseason skill |
| **E006** | V1 vs B0/B1/B2 on MAE and XI+Cap **means** | Beats B1/B2; does not beat B0 means (contaminated) |
| **E007** | After structural tags, where do points go? Horizon-6 vs V1_GW1 | H0 supported; H2 weak; 86% squad share is vs god-mode oracle |
| **E008** | Per-GW Spearman(xP, actual) | H0a: 10/38 and 34/38 flagged on the two primary seasons |
| **E009** | p_start calibration, XI 0-min, MAE \| 60+ | H0b at XI layer; new-club split confounded |
| **E013** | Do those qualitative verdicts hold on 2022/23–2023/24? | Yes for H0a, H0b (p90_fitted), H-v1-naive; H2 sign-flips |
| **E010** | Score live 2026/27 GW1 | completed (V1 measurement) |
| **E014** | LOSO p_start remap | **REJECT** |
| **E015** | Structural as-of-T minutes (`v2am_s`) | **PASS** → promoted (`v2am-s-baseline`) |
| **E016** | V2B multi-season rates vs V2A-M control | **REJECT** (MAE/Sp OK; Cap/XI0 fail 2/4) |
| **E016b** | XI movers under rates_v2b | **concentrated** (club-prior μ promotion) |
| **E017** | V2B-d prior→XI dampening (α=0.50) | **REJECT** (same FAIL seasons; dosage↓ but gates fail) |
| **E017b** | FAIL vs PASS entrant profiles | **concentrated** (prior+cold recent → 43% blank) |
| **E018** | V2B-e form eligibility gate (90/450) | **REJECT** (0/4 gates; branch retired) |
| **E018s** | Club-prior family A vs B synthesis | **B** (useful signal; unsafe under ILP) |
| **E019** | V2C role-transition minutes | **REJECT** (XI0↑; Cap/MAE fail) |
| **E019b** | Cap-FAIL vs PASS demoted leavers | **concentrated** (false-positive demotion) |
| **E020** | V2C-e cold-eligible demotion (recent4&lt;90) | **REJECT** (Cap↑; MAE✗ 4/4) |
| **E021** | V2D learned fixture coefficients | **REJECT** (MAE✓ Cap/XI0✗ 4/4) |
| **E021b** | Fixture XI mover toxicology | **concentrated** (cold cell 61% blank) |
| **E021c** | Cold-cell minutes × points | **mostly non-playing** (61% zeros; 60+ OK) |
| **E022** | Packaging: minutes-reliability of fixture μΔ | **PASS** vs raw v2d (not promote) |
| **E023** | Packaged v2d vs production fixtures=v1 | **REJECT** (XI0✗ 4/4; named risk) |
| **E011** | Season simulation with 1 FT/week | **queued** (needs transfer engine) |
| **E012** | Property tests for evaluation integrity | **PASS** (9/9 unittest) |
| **E024** | Packaged rates=v2b vs production rates=v1 | **REJECT** (Cap✗ 2/4; XI0✓) |
| **E024b** | Cap-FAIL vs PASS packaged rates movers | **concentrated** (wrong-player-when-playing) |
| **E025** | Cap-FAIL swap ranking concordance | **concentrated** (relative ranking ~47% vs ~75%) |
| **E026** | Control-μ near-tie (H-PACK1 branch) | **concentrated** (rank_err ~91% near+mid) |
| **E027** | H-PACK1 stability selection vs production | **REJECT** (1/4 PASS; binds 13–30%) |
| **E028** | Local substitution stability diagnostic | **reject** (local branch; margin-agnostic FAIL) |
| **E029** | Treatment-lift outcome profile | **concentrated (negative)** — no FAIL separator |
| **E030** | Objective alignment diagnostic | **concentrated (negative)** — portfolio anti-aligns on FAIL |
| **E031** | Objective decomposition (XI vs captain) | **concentrated** — XI-level sign flip on FAIL |
| **E032** | XI objective audit (oracle XI, μ vs utility) | **concentrated** — μ inversion; squad pool not XI-solve |
| **E033** | Squad pool / μ-inflation diagnostic | **concentrated** — wrong-15 pool dominates FAIL |
| **E034** | Squad entrant toxicology + boundary | **concentrated** — budget displacement signal |
| **E034b** | Forced-swap counterfactual | **concentrated** — tripwire re-equilibration; Δ_cascade=0 |
| **E034c** | Pairwise swap counterfactual | **concentrated** — layered pair + re-equilibration; chain closed |
| **E035** | Portfolio value decomposition | **concentrated** — g_treat cluster; MC hypothesis earned |
| **E036** | Contextual marginal admission value (H-MC1) | **concentrated (negative)** — MC ≡ U; V(S) suspect |
| **E037** | Portfolio value alignment (\(V_A\) vs \(V_B\)) | **concentrated (negative)** — V_B ≈ V_A; both anti-align FAIL |
| **E038** | Season payoff (rolling vs GW1-lock) | **concentrated** — Landing A; both negative FAIL |

E013 sits above E010 in the log because it was run on the research calendar
before the live deadline. It does not change Friday control.

---

## 9. What V1 is not

- A Gaussian points model. μ and σ summarise a discrete Monte Carlo sample.
- A recommendation product. The UI must not invent LOO deltas, sim quantiles,
  or per-strategy squads that `capture.py` never wrote. The live strategy
  board is an explicit re-solve with a caveat in the export JSON.
- A second optimiser for the Guehi/Haaland call. That call is the frozen
  audit.
- A claim that B0 is the truth. On many weeks it is closer to an oracle than
  a contemporaneous projection [2].

---

## 10. Citations

1. Fantasy Premier League. REST API. `https://fantasy.premierleague.com/api/`.
   Live bootstrap, fixtures, event live, and public entry resources.

2. Anasane, V. *Fantasy Premier League* (dataset). GitHub.
   `https://github.com/vaastav/Fantasy-Premier-League`.
   Historical `merged_gw.csv`, `fixtures.csv`, `teams.csv`, player identity
   (`code`), and official `xP`. Timing caveats on `xP` motivate excluding
   `ep_next` from historical snapshots and running E008.

3. Spearman, C. (1904). The proof and measurement of association between two
   things. *American Journal of Psychology*, 15(1), 72–101.
   Rank correlation used for player-level ranking skill and the E008 flag.

4. Naeini, M. P., Cooper, G. F., & Hauskrecht, M. (2015). Obtaining
   well-calibrated probabilities using Bayesian binning. *Proceedings of AAAI*.
   Equal-width bin ECE matches `calibration_error` in `engine/metrics.py`
   (five bins, weighted absolute gap between mean predicted probability and
   mean outcome).

5. Mitchell, S., O'Sullivan, M., & Dunning, I. *PuLP: A Linear Programming
   Toolkit for Python.* University of Auckland.
   `https://github.com/coin-or/pulp`

6. Forrest, J., & Lougee-Heimer, R. *CBC: COIN-OR Branch and Cut.*
   `https://github.com/coin-or/Cbc`
   MIP solver called by PuLP in `engine/optimize.py`.

No Dixon–Coles, Opta xG, or third-party FPL blog is cited as a method we
implemented. Price-based xG/xA priors are original heuristics in
`engine/project.py`.
