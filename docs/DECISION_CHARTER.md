# Decision charter

> **Which payoff are we optimizing, and which action are we taking?**

This document resolves the Landing A / Landing B fork **before** any V_C code or
transfer-engine work. It does not pick a winner — it names the questions, maps them
to existing harness behavior, and pre-registers how to discriminate them.

Related: [`PORTFOLIO_VALUE_SPEC.md`](PORTFOLIO_VALUE_SPEC.md), [`DECISION_ARCHITECTURE.md`](DECISION_ARCHITECTURE.md), [`LAB_LOG.md`](LAB_LOG.md).

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

## 7. V_C — gated (E038: Landing A; no automatic path)

E038 concentrated: **Landing A.** V_C is **not** the next default step.

Pursue V_C only with a **new pre-registered hypothesis** (not "re-squadding rescue").
If pursued, still requires minimal \(z\) state spec before code.

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

## 10. Current call

```text
CHARTER        Landing A (E038 concentrated)
CLOSED         E024–E038 promote path for rates_v2b
NOT NEXT       V_C without new hypothesis; horizon ILP promote
PRODUCTION     v2am_s + rates=v1 + fixtures v1 (unchanged)
```

---

## 11. Amendment protocol

To change primary estimand or primary action:

1. Append a dated note to this file (do not rewrite history)
2. Pre-register the next experiment in LAB_LOG
3. Do not retro-fit past E024–E037 verdicts
