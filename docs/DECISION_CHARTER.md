# Decision charter

> **Which payoff are we optimizing, and which action are we taking?**

This document records the estimand/action charter after E024–E038. **Landing A**
was adopted (E038). **`rates_v2b` promote is permanently closed** under the
current architecture (Phase 0). Post-E038 work forks into Research / Upstream /
Product — not a linear experiment ladder.

Related: [`PORTFOLIO_VALUE_SPEC.md`](PORTFOLIO_VALUE_SPEC.md), [`DECISION_ARCHITECTURE.md`](DECISION_ARCHITECTURE.md), [`LAB_LOG.md`](LAB_LOG.md), `ROADMAP.md`.

Numbers and verdicts: LAB_LOG wins on conflict.

---

## 1. What we know (E024–E037)

We localized portfolio anti-alignment on FAIL seasons:

```text
Not: packaging, captain, utility transform, ctrl-pool ranking, entrant toxicity,
     contextual admission (MC ≡ U), horizon scalar (V_B ≈ V_A)
Yes: treat μ can raise predicted utility while lowering realized GW Cap;
     large portfolio displacement (g_treat) predicts bad GW outcomes
```

**Closed value-functional class:** any \(V(S)\) that is a separable functional of
current \((\mu, U, \text{constraints})\) alone — including context and horizon mass.

**Open axis:** \(V(S, z)\) where \(z\) is extra state (transfers, bank, prices, chips)
not determined by current μ. That is **not** incremental to E036/E037; it is a new
problem formulation. Do not build without this charter.

---

## 2. The fork (decide before building)

| | **Landing A** | **Landing B** |
|---|---|---|
| **Claim** | GW-level portfolio value from projections cannot align in FAIL regimes | GW-Cap harness is the wrong stress test for a sequential game |
| **Success** | Honest GW ΔCap alignment (or proof it won't come) | Better season cumulative Cap, transfer ROI, or rank |
| **If true, imply** | Stay conservative on aggressive μ-driven re-squads; distrust g_treat moves | Redesign evaluation gates and estimand; V_C may be warranted |
| **V_C role** | Low priority | Natural (state + actions + multi-GW R) |
| **Risk** | Stops architecture search early | Scope → V5 transfer engine |

**Commitment rule:** pick a **primary estimand** and **primary action** before V_C.
E038 discriminates the fork descriptively; it does not implement V_C.

---

## 3. Primary action — what does the system decide?

| Action | Production today | E024–E037 harness |
|---|---|---|
| **Friday 15** (squad pick) | Yes — `engine.audit`, horizon squad ILP | Yes — `objective=next` squad ILP |
| **Weekly XI + captain** | Yes — re-solved on cached snapshot | Yes |
| **Transfers / hits / chips** | No optimizer | Not modeled |

**Charter default (until changed):** primary action = **squad pick + weekly XI/cap**
on a rolling as-of-T basis. Transfers are **out of scope** for the next experiment
unless this document is amended.

---

## 4. Primary estimand — what payoff matters?

| Estimand | Definition | Used where |
|---|---|---|
| **R_GW** | Realized Cap this GW (XI pts + captain bonus) | E024–E037 gates, E030–E037 diagnostics |
| **R_season** | Sum of R_GW over GWs 1–38 (fixed squad policy) | E038 (pre-registered) |
| **R_season_roll** | Sum of per-GW ΔCap with rolling re-solve each GW | E038 arm A |
| **R_season_lock** | Season Cap on GW1-locked 15, XI/cap re-solved each GW | E038 arm B |

**Harness history:** E024 FAIL/PASS gates use **per-season GW-level Cap** (rolling
re-solve). That is a **Landing A stress test** — myopic, aggressive, conservative
for promote decisions.

**Production posture:** horizon-6 squad utility suggests **partial Landing B intent**
(squad valued as multi-GW state) while evaluation remains GW-Cap-shaped.

---

## 5. What E024 FAIL means under each landing

| Landing | Interpretation of Cap-FAIL on 2022-23 / 2025-26 |
|---|---|
| **A** | Treat arm is genuinely worse for the estimand we care about (GW Cap). Do not promote. g_treat is a warning signal. |
| **B** | Treat may be wrong on GW stress test but acceptable on season objective. FAIL gate is conservative; need season-level evidence before promote/reject. |

**Frozen promote rule (unchanged):** do **not** promote `rates_v2b` on FAIL GW-Cap
evidence alone. PASS ≠ auto-promote.

---

## 6. Discriminating the fork — E038 (pre-registered)

**Question:** On FAIL seasons, is portfolio damage **GW-structural** (Landing A) or
**artifact of rolling re-squadding** (Landing B)?

| Arm | Policy | Season score |
|---|---|---|
| **A — rolling** | Re-solve squad each GW (E024 stack); sum ΔCap | Already in E037 GW rows |
| **B — GW1-lock** | Fix 15 from GW1; each GW re-solve XI+cap on as-of-T μ | Season Σ Cap_treat − Cap_ctrl |

**Primary (FAIL seasons):**

- sign(season_sum_ΔCap_rolling)
- sign(season_sum_ΔCap_gw1_lock)
- Does arm B differ materially in sign or magnitude from arm A?

**Branching (after E038):**

| Result | Charter update |
|---|---|
| Both negative on FAIL | **Landing A** strengthened — season pain, not just GW noise |
| Rolling negative, GW1-lock neutral/positive | **Landing B** strengthened — re-squadding is the stress; revisit gates |
| Both neutral/positive on FAIL | Revisit FAIL gate definition or treatment stack |
| PASS pattern differs | Report only; not for promote |

**Forbidden:** transfer simulation, V_C implementation, new μ, optimizer integration.

**Method:** `python scripts/e038_season_payoff.py`

---

## 7. V_C — gated until E039; Research lane owns structural V

E038 concentrated: **Landing A.** Separable \(V_A/V_B\) closed.

**E039 (2026-09-04)** is the pre-registered Research-lane entry for structurally
non-separable \(V(S,z,F)\). First artifact = counterfactual regret evaluator.
Optimizer / transfer engine still forbidden until E039 passes its primary gate
and a separate prereg amends this charter.

---

## 8. E038 result — charter stance (2026-09-02)

**Landing A adopted.** Both rolling and GW1-lock season ΣΔCap negative on FAIL:

| Season | rolling ΣΔCap | GW1-lock ΣΔCap |
|---|---:|---:|
| 2022-23 (FAIL) | −115 | −88 |
| 2025-26 (FAIL) | −13 | −383 |

Landing B rejected — fixing GW1 15 does not rescue; 2025-26 lock worse than rolling.

Primary estimand for promote: **R_GW / season cumulative Cap**. No `rates_v2b` promote.

---

## 9. Monitoring signals (production + research)

| Signal | Source | Use |
|---|---|---|
| **g_treat** | E035/E037 | Large displacement under treat μ → caution, not auto-reject |
| **portfolio_bad GW** | E030+ | Rolling GW stress |
| **FAIL season gate** | E024 | Promote bar (GW Cap) |
| **MC ≡ U** | E036 | Do not revisit admission scores under same U |

---

## 10. Permanent boundary — rates_v2b (Phase 0, 2026-09-04)

**`rates_v2b` is closed at the decision/season level under the current architecture.**

E024–E038 localized FAIL-regime season losses under both rolling and GW1-lock
policies. Predictive gains and PASS-season payoff are insufficient for promote.

**Reopening requires a new pre-registered hypothesis** — not a packaging retune,
α/q search, shrink variant, or “one more season look.” Do not mutate production
while choosing the next track.

**Promotion policy (all future candidates):**

```text
Prediction improvement without decision improvement = kill
```

MAE/Spearman alone never promote. Decision gates + season payoff required.
`g_treat` is a required **monitor/caution** on candidate reports — not an
optimizer feature.

---

## 11. Post-E038 fork — three tracks (not a linear ladder)

Experiments after E038 answer **different questions**. Do not collapse into
`E039 → E040 → …` as a single roadmap.

```text
                   E038
                    │
        ┌───────────┼────────────┐
        │           │            │
   RESEARCH      UPSTREAM      PRODUCT
        │           │            │
      E039       Role/Minutes   Chips
   structural V   (new hyp)     ROI
   regret gate   decision gate  frozen μ
        │           │            │
        └───────────┼────────────┘
                    │
              only successful
                branches
                    │
                 Transfers
                    │
             Full season agent
```

| Track | Question | First artifact | Gate |
|---|---|---|---|
| **Research** | What should \(V(S,z,F)\) mean? | Counterfactual regret evaluator (not an optimizer) | Candidate \(V\) must explain regret; \(V \neq \sum U_i\) in principle (survive E036) |
| **Upstream** | Better minutes/role beyond `v2am_s`? | New structural card — **not** E017 reopen | Same production stack, decision gates, `g_treat`, season payoff; no MAE-only promote |
| **Product** | First sequential FPL action? | Chip ROI under frozen `v2am_s + rates=v1` | \(E[Y_{\text{chip}}-Y_{\text{normal}}]\); then price → transfers |

**Discipline:** only **one implementation lane** active at a time. Parallel
pre-registration is fine; parallel coding is not.

**Product sequence (if that lane wins):** chips → price state → transfers →
full season planner. Do not jump to transfer ILP first.

**Research sequence (if that lane wins):** historical treatment → counterfactual
alternatives → realized regret → does candidate \(V\) explain regret? → **only
then** optimizer integration.

---

## 12. Institutional inventory

| Bucket | Contents |
|---|---|
| **Production** | `v2am_s` + `rates=v1` + fixtures `v1` |
| **Closed research** | `rates_v2b` promote path; packaging/stability/displacement/MC-under-same-U arcs (E022–E038) |
| **Research candidates** | Structural \(V_C\) / non-separable portfolio value (E039+); gated until prereg |
| **Upstream candidates** | Role-transition / availability dynamics (new hyp, E038 discipline) |
| **Product candidates** | Chips → price → transfers → season agent |

---

## 13. Current call

```text
CHARTER        Landing A (E038 concentrated)
CLOSED         rates_v2b promote; E039-A V_ns λ=0.5;
               E042-A club–position recent-minutes-share family;
               E043-A lagged PL short-turnaround-gap demotion family
UPSTREAM       fork open — distinct as-of-T signal only
TC PRODUCT     E040-A wired (fpl.py tc)
BB PRODUCT     E041-A wired (fpl.py bb)
PRODUCTION     v2am_s + rates=v1 + fixtures v1
NOT NEXT       E042/E043 family retunes; target-GW KO without dated fixture book
```

---

## 14. Amendment protocol

To change primary estimand, primary action, or reopen a closed branch:

1. Append a dated note to this file (do not rewrite history)
2. Pre-register the next experiment in LAB_LOG
3. Do not retro-fit past E024–E038 verdicts
4. Do not change production while the choice is open

---

## 15. E039 — Research lane activated (prereg 2026-09-04)

Phase-0 fork choice: **Research**. See `LAB_LOG.md` E039.

**Contract (frozen):**

```text
HYPOTHESIS
Realized admission regret contains information from z and F that cannot be
represented by any monotone transform of separable treatment utility U.

NULL
Novelty-fail:  V ranking ≡ monotone(U) on feasible admissions → kill (E036 class)
Decision-fail: V differs but fails primary gate → kill/park; return to Phase-0 fork

ESTIMAND
regret(i|S,T) = Y(best feasible alt|S,T) − Y(admit i|S,T)

PRIMARY GATE
V ranks feasible admissions better than U on FAIL historical eval,
AND ranking is not monotone-equivalent to U.

SECONDARY
GW Cap / XI+Cap / season payoff (report only).

LEAKAGE
HARNESS_SPEC as-of-T allowlist only. No post-GW info in z, F, V, or scores.

FORBIDDEN AFTER PEEK
No λ / V retune / V_D·V_E in same peek / optimizer / outcome-motivated features.

FIRST ARTIFACT
Counterfactual regret evaluator. No ILP. No new model. No production changes.

BEFORE HISTORICAL GATE
Append dated LAB_LOG amendment naming ONE candidate V formula.
```

Upstream and Product stay **roadmap-only** until E039’s stop rule fires or is amended here.

---

## 16. E039-A — Candidate \(V\) locked (2026-09-04); **KILL** after gate

Amendment to §15. Full math: `LAB_LOG.md` § E039-A; `PORTFOLIO_VALUE_SPEC.md` §14.

```text
CANDIDATE   E039-A / V_ns
FORMULA     Σ_{i in XI} U_i  −  0.5 × Σ_f C(n_f, 2)
RESULT      concentrated (negative) KILL
            novelty YES (27% sign disagree FAIL)
            decision NO (spearman V=-0.084 < U=+0.066 FAIL both60)
NEXT        Phase-0 fork open; no optimizer; no λ retune
```

---

## 17. E040 — Product lane activated (prereg 2026-09-05)

Phase-0 fork choice after E039-A KILL: **Product**. See `LAB_LOG.md` E040.

**Primary question:** Does the as-of-T production signal contain sufficient information
to select a Triple Captain action whose cumulative realized Cap is robustly better
than both a no-chip baseline and a simple fixed-calendar benchmark?

**Arm roles (frozen; B1 ≠ C):**

| Arm | Definition | Purpose |
|---|---|---|
| **B0** | Never TC; normal captain | Floor |
| **B1** | TC once at fixed \(g^\star\) (no \(U\)) | Non-model calendar stake |
| **C** | \(t^*=\arg\max_{t\in W} U_{\mathrm{capt}}(t)\); TC once at \(t^*\) | Projection-informed timing |

\[
W = \{1,\ldots,38\}
\]

unless `HARNESS_SPEC` excludes a GW for integrity. Exact \(g^\star\), tie-break
(lowest GW, then lowest `element_id`), squad objective, and aggregate gate rule
are frozen in a **dated LAB_LOG amendment** before the historical run.

**Stack:** `v2am_s + rates=v1 + fixtures v1`. No new μ.

**First artifact:** historical B0/B1/C season-Cap evaluator. No live UI, no optimizer
changes, no BB/FH/WC in this peek.

**Stop:** E040-TC fail kills this chip wedge only; return to Phase-0 fork or prereg BB.

---

## 18. E040-A — Policy freeze (2026-09-05); **SURVIVES** after gate

```text
g*           = 20
W            = {1..38}
OBJECTIVE    = next
U_capt(t)    = next_utility of pick_captains at GW t
C            = TC at argmax_t U_capt(t); tie → lowest GW
B1           = TC at GW 20 (no U)
RESULT       SURVIVES AGG+FAIL
             Σ4 R(C)=8275 > B0 8218 >? B1 8251 (C>B1)
             FAIL Σ R(C)=4057 >= B0 4028 and >= B1 4038
NEXT         product-wiring prereg OR BB wedge; no silent UI ship
```

Details: `LAB_LOG.md` § E040-A.

---

## 19. E040-A product surface (wired 2026-09-05)

TC recommendation is an **implementation of the frozen E040-A contract**, not a new experiment.

```text
MODULE       engine.e040_tc_policy (shared offline ↔ product)
CLI          python fpl.py tc | python -m engine.e040_tc_recommend
CLAIM        Under the frozen E040-A policy, recommend TC in the GW where
             projected captain utility is highest.
INDEPENDENCE Independent of BB (E041-A); not a combined chip calendar;
             joint feasibility not claimed (§23)
LIVE         Past: as-of-t when rebuildable. Current+future: under I_N only.
GATE         Historical t*/captain must match E040 evaluator artifacts
             (tests/test_e040_tc_policy.py).
FORBIDDEN    DGW heuristics; thresholds; confidence; new μ; BB/FH/WC;
             joint chip calendar; policy retune without new prereg.
```

Any policy change → new preregistered experiment, not a wiring tweak.

---

## 20. E041 — Bench Boost ROI (prereg 2026-09-05)

Product lane continues after TC wiring. **Different capability:** bench portfolio value.

**Primary question:** Does as-of-T production signal select a BB action whose season Cap
robustly beats no-BB **and** a fixed-calendar stake?

**Arms (B1 ≠ C):**

| Arm | Definition |
|---|---|
| **B0** | Never BB |
| **B1** | BB once at fixed \(g^\star\) (no \(U\)) |
| **C** | \(t^*=\arg\max_{t\in W} U_{\mathrm{bench}}(t)\); BB once at \(t^*\) |

\[
U_{\mathrm{bench}}(t)=\sum_{i\in\mathrm{bench}(t)} U_i^{\mathrm{next}}
\]

after production `solve_squad` + XI. \(W=\{1,\ldots,38\}\). Exact \(g^\star\), tie-break,
and Cap_BB definition frozen in dated LAB_LOG amendment before the historical run.

**Independent of TC** (not a joint planner). No BB UI until gate survives.

See `LAB_LOG.md` § E041.

---

## 21. E041-A — Policy freeze (2026-09-05); **SURVIVES** after gate

```text
g*           = 20
W            = {1..38}
OBJECTIVE    = next
U_bench(t)   = sum next_utility over sol.bench
C            = BB at argmax_t U_bench(t); tie → lowest GW
B1           = BB at GW 20 (no U)
RESULT       SURVIVES AGG+FAIL
             Σ4 R(C)=8300 > B0 8218 and > B1 8263
             FAIL Σ R(C)=4086 >= B0 and >= B1
             C beat B1 in every season
NEXT         optional BB wiring (mirror E040-A); no silent UI ship
```

Details: `LAB_LOG.md` § E041-A.

---

## 22. E041-A product surface (wired 2026-09-05)

BB recommendation is an **implementation of the frozen E041-A contract**, not a new experiment.

```text
MODULE       engine.e041_bb_policy (shared offline ↔ product)
CLI          python fpl.py bb | python -m engine.e041_bb_recommend
CLAIM        Under the frozen E041-A policy, recommend BB in the GW where
             projected bench utility is highest.
INDEPENDENCE Independent of TC (E040-A); not a combined chip calendar;
             joint feasibility not claimed (§23)
LIVE         Same I_N semantics as E040-A (§19)
GATE         Historical t*/U_bench match E041 artifacts (tests/test_e041_bb_policy.py)
FORBIDDEN    Joint TC+BB planner; bake U_bench into squad ILP; policy retune
```

---

## 23. Chip product surfaces — independence + freeze checklist (2026-09-05)

TC (E040-A) and BB (E041-A) are **separately** identified policies. Outputs must state
that recommendations are independent and may conflict; using both at their respective
\(t^\star\) is **not** a validated joint policy.

```text
CHECKLIST (do not change without new prereg)
  policy_id          E040-A / E041-A
  claim + independence in CLI text and JSON
  artifact parity    tests/test_e040_tc_policy.py, tests/test_e041_bb_policy.py
  optional data skip tests.historical_data.unavailable_reason only
  production μ       unchanged (v2am_s + rates=v1 + fixtures v1)
FORBIDDEN            joint chip calendar; FH/WC in these surfaces; g* retune
```

Chip lane **paused** after E041. Next product chip requires a new prereg.

---

## 24. E042 — Upstream club–position minutes share (prereg 2026-09-05)

**Lane:** Upstream. One implement lane.

**Signal:** as-of-T minutes share \(s_i(T)\) within club+position (see LAB_LOG E042).

**E042-A freeze (2026-09-05) — before code:**

```text
INVARIANT     same Snapshot + decision stack; only minutes base via share
W             = 4
λ             = 0.35
map           b1=(1-λ)b0+λ·MAX_BASE·s; clip to [0.04, 0.85]; then × availability
b0            full v2am_s base (cold/hot UNCHANGED)
identity      T=1; |G|<2; denom=0; no GWs on current club in window
minutes src   merged_gw element/GW/minutes/team; team must match current club
control       minutes_version=v2am_s
treat         minutes_version=v2am_share
FAIL          {2022-23, 2025-26}
GATES         XI0 non-inferior 4/4; MAE_60+ non-worse 4/4;
              FAIL Cap non-neg each; AGG Cap non-worse; g_treat report
KILL          MAE-only; FAIL Cap loss; any E015/E019/E020 reopen
NO TUNE       λ, W, floors, cold/hot after peek
RESULT        KILL (2026-09-05) — XI0✗ MAE✗ FAIL-Cap✗; no promote; no λ/W retune
FAMILY        CLOSED (2026-09-06) — no W/λ/caps/blend-shape variants of the same
              current-club/position recent-minutes-share observable; reopen only
              with a distinct as-of-T causal signal (not recency/role-share retune)
```

Details: `LAB_LOG.md` § E042-A gate + family closure.

---

## 25. E043 — PL schedule-pressure minutes (prereg 2026-09-06)

**Lane:** Upstream. One implement lane.

**E043-A freeze (2026-09-06) — before code:**

```text
NAME          lagged short-turnaround load (NOT target-GW rest)
SIGNAL        d_prev_gap = (prior_utc - prior2_utc).total_seconds()/86400
              prior, prior2 = last two PL kickoffs with event < T
TRIGGER       d_prev_gap < 5.0  →  demote eligible outfield incumbents
ELIGIBLE      outfield & season minutes >= 800; GKP identity
MAP           b0=v2am_s; b1=min(b0, 0.60) if trigger else b0; × availability
FORBIDDEN     target-GW KO; deadline rest; forward density; non-PL; E042 share
TREAT         minutes_version=v2am_sched
CONTROL       minutes_version=v2am_s
GATES         XI0 4/4; MAE_60+ 4/4; FAIL Cap each; AGG Cap; g_treat report
NO TUNE       5.0 / 0.60 / 800 after peek
PROVENANCE    completed fixtures only → as-of-T reconstructible on panel
RESULT        KILL (2026-09-06) — XI0✗ MAE✗ FAIL-Cap✗; no promote; no threshold retune
FAMILY        CLOSED (2026-09-06) — lagged PL short-turnaround-gap demotions of
              p_start from completed PL KOs only; no gap/cap/eligibility/map
              variants on same observable; reopen needs distinct signal (+ dated
              fixture book if target-fixture timing)
```

See `LAB_LOG.md` § E043-A gate + family closure.
