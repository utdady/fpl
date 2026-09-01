# Decision architecture

> **What quantity is missing from standalone player μ when evaluating a constrained 15-player portfolio?**

This document is the specification earned by E030–E034c. It does **not** propose a fix.
It names what the system optimizes today, what realized payoff actually is, where they
diverge, and what evidence would justify changing the decision layer.

Numbers and verdicts live in [`LAB_LOG.md`](LAB_LOG.md). If this file disagrees with
the log, the log wins.

---

## 1. Reading order

| Document | Job |
|---|---|
| [`LAB_LOG.md`](LAB_LOG.md) | Hypotheses, E001–E034c, tables, verdicts (append-only) |
| **This file** | Decision-layer spec: current architecture, failure modes, candidate quantities |
| [`PROJECT.md`](PROJECT.md) | Full methods, math, experiment map |
| [`HARNESS_SPEC.md`](HARNESS_SPEC.md) | As-of-T reconstruction and pass/fail gates |
| [`FORMAL.md`](FORMAL.md) | What can be proved vs what statistics prove |

---

## 2. What the system optimizes today

### 2.1 Pipeline

```text
per-player projection (μ, σ, p_start)
        ↓
scalar utility U_i = f(μ_i, σ_i, p_start_i, strategy)   # standalone per player
        ↓
squad ILP: max Σ w_i · U_i   subject to budget, positions, club limit
        ↓
XI ILP: max Σ U_i (starters) on chosen 15
        ↓
captain: argmax U_i among XI (double-count in Cap objective)
```

Production and harness treatment stack (frozen E024–E034c):

```text
minutes=v2am_s + rates=v1 (control) vs rates_v2b (treat)
objective=next; strategy=balanced; seed=7
fixtures=v1
```

### 2.2 Operational definition of portfolio value

Today the optimizer's portfolio value is **not** realized Cap points. It is:

**Squad stage** (`engine/optimize.py`, `BENCH_WEIGHT = 0.12`):

\[
V_{\text{squad}}(S) = \sum_{i \in S} \bigl( w_i \cdot U_i \bigr), \quad w_i \in \{0.12,\, 0.88 \}
\]

where starter/bench weights are chosen by the same ILP (not post-hoc).

**XI stage** (after squad is fixed):

\[
V_{\text{XI}}(S) = \sum_{i \in \text{XI}(S)} U_i
\]

**Captain stage**:

\[
V_{\text{Cap}}(S) = V_{\text{XI}}(S) + U_{\text{captain}}
\]

**Realized payoff** (what we score in harness):

\[
R_{\text{Cap}}(S) = \text{XI points} + \text{captain bonus points}
\]

The decision architecture effectively assumes:

\[
V_i \approx \mu_i \quad \Rightarrow \quad \arg\max_S V(S) \approx \arg\max_S R(S)
\]

E030–E034c show this approximation **breaks in certain regimes** even when per-player
μ improves (MAE/Spearman) and players actually play.

### 2.3 What is *not* in V(S) today

- Budget opportunity cost of selecting \(i\) vs the best alternative at each position
- Replacement value: what you give up elsewhere in the portfolio
- Positional scarcity / depth
- Multi-GW transfer flexibility, hits, chips
- Portfolio correlation or variance
- Uncertainty of **relative** ranking (only scalar U per player)
- Player interaction effects
- Context of admission: \(MC_i(S) = V(S \cup \{i\}) - V(S)\) vs standalone \(U_i\)

---

## 3. What realized payoff actually is

FPL does not reward owning a player in isolation. Realized value is:

- **Constrained**: exactly 15 players, formation rules, £100m budget, ≤3 per club
- **Compositional**: XI selection and captain double-count change which μ mass matters
- **Sequential**: transfers, price changes, and multi-GW planning (ignored by `objective=next`)
- **Regime-dependent**: the same μ improvement can help or hurt depending on season context

The harness measures \(R_{\text{Cap}}\) on historical actuals. The optimizer maximizes
\(V_{\text{Cap}}\) under projected \(U_i\). Alignment between them is an **empirical**
question, not guaranteed by better μ.

---

## 4. Evidence chain (E030 → E034c)

Displacement localization is **closed**. Summary:

| ID | Finding |
|---|---|
| **E030** | On FAIL: mean ΔU > 0, mean ΔCap < 0; corr(ΔU, ΔCap) ≈ −0.2. Portfolio-level sign flip. |
| **E031** | Flip is XI-level; captain channel secondary; oracle captain does not fix. |
| **E032** | corr(ΔU, Δμ) ≈ +0.99; μ tracks predicted utility but **realized inverts** on FAIL. Not a utility-transform bug. |
| **E033** | Wrong-15 pool dominates (~74% of loss); treat rank on ctrl 15 ≈ neutral (−0.05). |
| **E034** | Entrants not individually toxic; budget displacement — entrants worse than leavers in context (vs_mean_leaver −0.51 FAIL). |
| **E034b** | Single forced entrant → full treat 15; Δ_cascade = 0 always. Tripwire re-equilibration. |
| **E034c** | Layered: Δ_pair ≈ −1.0, Δ_reeq ≈ −2.5, Δ_full ≈ −3.5 on FAIL. G_treat = 1.35 vs G_ctrl = 0.39 — treat objective **prefers** full composition. |

### 4.1 The core tension (preserve forever)

On FAIL seasons, for treatment vs control:

```text
G_treat > G_ctrl          optimizer rationally prefers treat portfolio under treat μ
Δ_full < 0                  realized Cap is worse
```

The optimizer is **not malfunctioning**. It is making a rational decision under an
objective that is **empirically misaligned** with realized portfolio payoff in certain
regimes. This is **objective incompleteness**, not "bad players" or "bad optimizer."

### 4.2 Mechanism (E034c decomposition)

```text
Treatment μ shift
   ↓
entrant replaces better contextual option     Δ_pair ≈ −1.0
   ↓
ILP re-equilibrates entire 15                 Δ_reeq ≈ −2.5
   ↓
full treatment outcome                        Δ_full ≈ −3.5
```

Re-equilibration is larger on average but not universal (~55% of pairs have
|Δ_reeq| > |Δ_pair|). Damage is **layered**, not single-cause.

### 4.3 Marginal value hypothesis (not implemented)

The current model uses standalone \(U_i\). FPL admission value is closer to:

\[
MC_i(S) = V(S \cup \{i\}) - V(S)
\]

E034/E034c are crude probes of this gap. **Do not implement MC in the optimizer**
until E035 identifies which portfolio quantity discriminates failure. MC is a
mechanism hypothesis, not a validated fix.

---

## 5. Known failure modes

| Mode | Evidence | Implication |
|---|---|---|
| **Regime anti-alignment** | E030 corr flip FAIL vs PASS | Better μ can worsen portfolio on some seasons |
| **μ inversion** | E032 oracle XI still negative on FAIL | Problem is not XI solver or captain interface alone |
| **Wrong-15 selection** | E033 ~74% loss from pool | Scalar ranking on ctrl 15 nearly neutral; squad composition matters |
| **Budget displacement** | E034 vs_mean_leaver | Context of admission matters, not entrant toxicity |
| **Tripwire re-equilibration** | E034b Δ_cascade = 0 | One entrant triggers global portfolio jump |
| **Objective gap drives jump** | E034c G_treat | ILP prefers full treat composition under treat μ |
| **Near-tie degeneracy** | E026 ~91% FAIL rank_err in near+mid buckets | Small μ gaps → unstable selections (stability branch closed E027–E028) |

---

## 6. Candidate missing quantities (unranked)

Do **not** choose one yet. Each is a hypothesis to test descriptively in E035.

| Candidate | Intuition | Example proxy (descriptive only) |
|---|---|---|
| **Budget opportunity cost** | £ spent on \(i\) forecloses better options elsewhere | Δ£ vs best same-pos alternative; budget slack after swap |
| **Replacement value** | Value of best player not selected at each position | max Δμ of non-selected same-pos player in pool |
| **Positional scarcity** | Thin positions amplify displacement | entrant rank − leaver rank within position; depth gap |
| **Bench value** | 4 bench slots carry real but discounted mass | bench μ sum treat vs ctrl; bench Δμ |
| **Portfolio composition shift** | Global rearrangement beyond pair | n_squad_diff, overlap, G/G₀ from E034c |
| **Near-tie / degeneracy** | Optimizer indifferent among near-equal options | ε-margin bucket from E026 on ctrl gaps |
| **Squad–XI coherence** | Squad chosen for weighted objective, XI for flat U | squad_xi_agree rate; Δ between squad and XI objective |
| **Transfer flexibility** | Price/route lock-in (multi-GW) | not measurable under `objective=next`; deferred |
| **Portfolio correlation** | CS covariance, team stacking | deferred to V4 roadmap |
| **Relative ranking uncertainty** | σ matters for ties, not just mean | gap / σ at swap boundary |

---

## 7. What would count as evidence (per candidate)

Before any mechanism is built, a candidate quantity must pass **descriptive** gates:

1. **Discriminates within FAIL treatment arm**: separates portfolio-bad GWs from portfolio-good GWs on the same season (not just "FAIL vs PASS" globally).
2. **Survives sign check**: direction matches economic intuition (e.g. higher replacement value → more displacement risk).
3. **Not collinear with Δμ alone**: incremental over mean Δμ or n_changes.
4. **Architecture vs treatment-specific**: compare proxy on ctrl squads vs treat squads; if only treat shows signal, may be μ-distortion not architecture-intrinsic.
5. **No post-hoc winner picking**: pre-registered primary discriminator; no fishing across 10 proxies on full panel.

**Forbidden as evidence:**

- "Proxy X correlates best on FAIL" → auto-add to objective
- Fitting λ, ε, or packaging dose after peeking
- Promoting on PASS seasons alone
- Implementing \(MC_i(S)\) in optimizer before E035 concentrated

---

## 8. E035 results (2026-09-01)

E035 ran the pre-registered proxy discrimination. Key findings:

| Finding | Implication |
|---|---|
| **g_treat** AUROC 0.73 on FAIL | Treat-utility gap (full vs ctrl composition) best discriminates portfolio_bad |
| Collinear cluster | g_treat ≈ ΔU_pred ≈ n_changes ≈ near_tie_frac (r up to 0.74) |
| replacement_value weak | AUROC 0.57 FAIL; not the missing quantity in isolation |
| mean_vs_leaver inverted | AUROC 0.21 — realized swap quality anti-predicts bad (μ inversion) |
| FAIL ≈ PASS on top proxies | Architecture-intrinsic, not treatment-only distortion |

**Branch:** → **E036 / H-MC1** contextual marginal admission value (pre-registered below). Phase A diagnostic only; no optimizer integration.

---

## 9. H-MC1 — Contextual marginal admission value (E036 pre-registered)

> **Standalone player value is insufficient for constrained FPL squad construction; the decision should account for the value of a player conditional on the portfolio they are entering.**

E035 showed the strongest discriminator is **treat-induced portfolio displacement** (g_treat cluster), not replacement value or realized entrant-leaver quality. H-MC1 tests whether **contextual marginal contribution** ranks boundary admissions better than standalone \(U_i\) — using frozen μ, realized outcomes as the judge.

### 9.1 What we are not doing yet

- Implementing \(MC_i(S)\) in the squad ILP (Phase C only if Phase B concentrates)
- Adding a "justification" or packaging score on top of MC
- Changing projections, minutes, fixtures, or rates
- Penalizing portfolio movement (large moves can be good on PASS)

### 9.2 Minimal definition of \(V(S)\)

Frozen for E036 Phase A — same object the optimizer already uses:

\[
V(S) = \text{squad-weighted treat utility post-XI-solve}
\]

(`BENCH_WEIGHT = 0.12`; `solve_xi` + starter/bench weighting on **treat** projections)

For control portfolio \(S_{\text{ctrl}}\) and same-position swap pair \((E, L)\):

\[
MC_E = V(S_{\text{ctrl}} \setminus L \cup E) - V(S_{\text{ctrl}})
\]

Computed by manual squad swap + `solve_xi` on treat utility (no squad ILP re-solve), matching E034c pair arm.

Standalone comparator: \(\Delta U = U_E - U_L\) (treat next_utility).

### 9.3 Phases (frozen)

```text
Phase A  estimate MC at admission boundary (this experiment)
Phase B  test MC ranking vs U ranking on realized portfolio improvement
Phase C  integrate into optimizer (only if Phase B concentrates; separate pre-reg)
```

**Circularity guard:** Phase A/B use **realized** Cap / swap pts as outcomes. Do not use treat-\(U\) improvement as the success metric for MC.

### 9.4 E036 scope lock

```text
stack:     v2am_s + packaged rates_v2b (treat) vs rates=v1 (ctrl)
           objective=next; strategy=balanced; seed=7
unit:      same-position (E,L) swap pairs at ctrl→treat squad boundary
filter:    both>=60 actual minutes (E025 convention)
arms:      delta_mc = MC_E - MC_L;  delta_u = U_E - U_L;  realized dpts = pts_E - pts_L

primary:   concordance on FAIL pairs:
             sign(delta_mc) vs sign(dpts)  vs  sign(delta_u) vs sign(dpts)
           report % concordant, rank correlation (Spearman) per gate

secondary (report only, not for branching):
  GW-level: sum(MC_entrants) - sum(MC_leavers) vs delta_cap
  PASS-season pairs (architecture-intrinsic check)
  near-tie bucket stratification (E026 cuts: 0.25 / 0.75 on ctrl mu gap)

forbidden:  squad ILP rewrite; MC in optimizer; new mu/packaging/lambda;
            MC + justification score; promote on PASS alone
```

### 9.5 Branching (after E036 only)

| Result | Next step |
|---|---|
| MC concordance > U concordance on FAIL (both60) | Phase B concentrated → integration spec (not code) |
| MC ≈ U on realized | Problem is \(V\) itself, not admission ranking under same \(U\) |
| MC worse than U | Contextual valuation under treat-\(U\) is not the fix |
| MC helps FAIL only, not PASS | Treatment-specific; revisit upstream μ, not architecture |

### 9.6 Method

`python scripts/e036_contextual_marginal.py` (not yet implemented)

---

## 10. Closed branches (do not reopen without new hypothesis)

```text
E024–E035   selection packaging / proxy decomposition
```

Production unchanged: `v2am_s` + `rates=v1` + fixtures `v1`.

Do **not** promote `rates_v2b` on FAIL evidence. PASS ≠ auto-promote.

---

## 11. Roadmap relationship

| Roadmap item | Status relative to this spec |
|---|---|
| **V2B rates** | REJECT; upstream rate/club-prior family retired |
| **Packaging** | CLOSED (availability risk only) |
| **V3 calibration** | orthogonal; does not fix portfolio architecture |
| **V4 correlation-aware optimizer** | one candidate quantity; deferred until E036 |
| **V5 multi-GW engine** | transfer flexibility candidate; deferred |
| **Decision architecture (this doc)** | **current research front** |
| **E036 / H-MC1** | **pre-registered** — contextual marginal admission value, Phase A diagnostic |

The next productive step is **E036 Phase A** (MC vs standalone \(U\) on realized swap concordance),
not another packaging rule or ε retune.
