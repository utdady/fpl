# Portfolio value functional — specification

> **Define and validate the correct portfolio value functional \(V(S)\).**

This document is the research specification earned by E030–E036. It does **not**
implement a new optimizer. It names what \(V(S)\) should estimate at decision time,
how that differs from the harness evaluation metric, and how to discriminate candidate
functionals **without circular optimization**.

Verdicts and numbers: [`LAB_LOG.md`](LAB_LOG.md). Decision-layer history:
[`DECISION_ARCHITECTURE.md`](DECISION_ARCHITECTURE.md). Methods: [`PROJECT.md`](PROJECT.md).

---

## 1. Research problem

The projection stack can improve per-player μ (MAE, Spearman) while **worsening**
realized portfolio outcomes in certain regimes (E030). E036 showed this is **not**
fixable by contextual admission ranking under the current \(V(S)\): \(MC \equiv U\) on
100% of boundary pairs.

The missing abstraction is not "better player score." It is:

```text
projection μ
      ↓
portfolio valuation V(S)    ← undefined / misaligned today
      ↓
squad / XI / captain decision
```

**Core question:**

> What quantity at gameweek \(t\), observable without future information, should
> \(V(S)\) estimate such that portfolios with higher \(V(S)\) tend to produce better
> realized FPL payoff?

This is an **estimand** question, not a model-version question. Do not conflate it with
"build V2 rates" or "add another packaging layer."

---

## 2. What is ruled out (E024–E036)

Do not reopen without a new pre-registered hypothesis.

| Branch | Verdict | Implication |
|---|---|---|
| Selection packaging (E024–E029) | closed | q(Δμ), lift reliability, global ε |
| Stability / margin (E026–E028) | closed | near-tie packaging does not fix FAIL corr |
| Displacement (E030–E034c) | closed | layered pair + re-equilibration |
| Proxy decomposition (E035) | concentrated | g_treat cluster; replacement/budget weak |
| H-MC1 contextual marginal (E036) | concentrated (negative) | MC ≡ U; admission ranking not the lever |

**Practical permission:** stop inventing cleverer admission scores under the same \(U\).

---

## 3. Terminology (keep separate)

| Term | Meaning | Example today |
|---|---|---|
| **Projection** \(\mu_i\) | Per-player expected points from model | `next_mu`, `horizon_mu` |
| **Standalone utility** \(U_i\) | Strategy transform of μ, σ, p_start | `next_utility`, `horizon_utility` |
| **Portfolio value** \(V(S)\) | Scalar score for squad \(S\) used in decisions | weighted Σ \(w_i U_i\) post-XI |
| **Realized payoff** \(R(S)\) | What actually happened | XI pts + captain bonus |
| **Harness metric** | How we judge experiments post-hoc | ΔCap, MAE, Spearman |
| **Estimand** | What \(V(S)\) should predict at decision time | *to be chosen* |

**Forbidden conflation:** setting \(V(S) := \mathbb{E}[R(S) \mid \text{actuals}]\) because
that is the harness score. Realized Cap is the **evaluation** target for validating an
estimand, not automatically the **optimization** target.

---

## 4. Decision-time information set \(\mathcal{I}_t\)

At as-of-T (harness freeze), \(V(S)\) may depend only on:

- Snapshot fields permitted at cutoff \(t\) ([`HARNESS_SPEC.md`](HARNESS_SPEC.md))
- Projections \(\mu, \sigma, p\_\text{start}\) from frozen stack (`v2am_s`, rates, fixtures)
- Squad \(S\) and FPL constraints (budget, positions, club limit)
- Strategy label (`balanced`, `safe`, …)

\(V(S)\) must **not** depend on:

- Future actual points or minutes
- Post-deadline official xP (E008 leakage class)
- Outcomes from other model arms being compared (evaluation integrity, E012)

---

## 5. What the system uses today (two objectives)

| Context | Squad ILP objective | Notes |
|---|---|---|
| **Production live / audit** | `horizon` (6-GW `horizon_utility`) | E002 freeze; `engine.audit` |
| **E024–E036 treatment harness** | `next` (`next_utility`) | deliberate myopic stress test |

Both build \(V(S)\) as **additive separable** utility:

\[
V(S) \approx \sum_i w_i(S)\, U_i
\]

with \(w_i \in \{0.12, 0.88\}\) from squad+XI ILP (`BENCH_WEIGHT`). E036 proved this
structure has **no interaction terms** sufficient to make contextual admission differ
from standalone \(U_i\) at the boundary.

Any new \(V(S)\) candidate must state explicitly whether it replaces production
`horizon`, harness `next`, or both.

---

## 6. Candidate portfolio value functionals (unranked)

Test **descriptively** before any optimizer integration. Do not combine until one
candidate concentrates.

### A. Next-GW value \(V_A\)

**Estimand:** expected Cap contribution over the imminent GW.

**Operational proxy (decision-time):**

\[
V_A(S) = \sum_{i \in \text{XI}(S)} U_i^{\text{next}} + U_{\text{captain}}^{\text{next}}
\]

(same as current harness treat objective after XI+cap solve)

**Prior art:** E024–E036 entire stack; E030 sign flip on FAIL.

**Discriminating question:** Already failed as alignment target — retained as **control arm**.

---

### B. Multi-GW state value \(V_B\)

**Estimand:** value of holding squad \(S\) as a **state** over horizon \(H\) GWs, not
just next-GW XI points.

**Operational proxy (decision-time):**

\[
V_B(S) = \sum_{i \in S} w_i\, U_i^{\text{horizon}(H)}
\]

with \(H=6\) matching production (`horizon_utility`).

**Prior art:** E007 `V1` vs `V1_GW1` (same μ, `horizon` vs `next` squad ILP):
+2–3 pts/GW median in some seasons, **−0.48 in 2022/23** — inconsistent sign.
Verdict: H2 weak; not shelved forever, but not a proven fix.

**Discriminating question:** On frozen μ, does \(V_B(S_{\text{treat}}) - V_B(S_{\text{ctrl}})\)
align with realized ΔCap better than \(V_A\) on FAIL? (Descriptive correlation only.)

---

### C. Transfer- and option-adjusted value \(V_C\)

**Estimand:** value of \(S\) including **future maneuverability** — budget slack, price
routes, bench cover for hits, chip timing.

**Operational proxy (decision-time):** *not fully defined.* Requires explicit state
variables not in current snapshot:

- remaining budget / price deltas
- transfer count, hit budget
- multi-GW bench emergency cover

**Prior art:** ROADMAP V5; E035 deferred transfer flexibility.

**Discriminating question:** Cannot test until minimal state vector is specified.
**Phase 0 for C:** write state variables only; no harness.

---

### D. Portfolio-relative / interactive value \(V_D\)

**Estimand:** value not reducible to \(\sum_i f(U_i)\) — interactions, correlation,
positional complementarity.

**Operational proxy:** MC under a **non-separable** \(V\). E036 tested MC under
separable \(V\) and got MC ≡ U.

**Discriminating question:** Any \(V_D\) must demonstrate **MC ranking ≠ U ranking**
on boundary pairs before optimizer work. Otherwise it collapses to A.

---

### E. Realized-payoff predictor \(V_E\)

**Estimand:** \(\mathbb{E}[R_{\text{Cap}}(S) \mid \mathcal{I}_t]\) — directly predict
harness payoff from decision-time features.

**Risk:** training \(V_E\) on realized Cap without careful as-of-T discipline becomes
post-hoc fitting. Acceptable only as **diagnostic upper bound** (e.g. oracle μ),
not as production objective without out-of-sample protocol.

**Discriminating question:** Does an oracle-μ \(V_E\) upper bound separate FAIL
portfolio-bad from good? (E032: oracle XI still negative on FAIL — suggests even
perfect μ does not fix regime inversion at XI layer alone.)

---

## 7. E035 + E036 synthesis (what we know about movement)

| Observation | Interpretation |
|---|---|
| g_treat AUROC 0.73 (FAIL) | Large treat-induced displacement predicts portfolio_bad |
| g_treat AUROC 0.67 (PASS) | Movement is **aggressiveness**, not inherently bad |
| MC ≡ U; 42% concordance | Re-ranking under same \(V\) does not fix realization |
| mean_vs_leaver inverted | Realized swap quality anti-predicts under current μ |

**Preserved sentence:**

> Large portfolio moves under treat μ are detectable; they are not inherently wrong;
> but the utility field that justifies them is empirically misaligned in FAIL regimes.

A new \(V(S)\) must answer **when** a large move is justified — not merely penalize movement.

---

## 8. How to discriminate candidates (no circular optimization)

**Phase 0 (this spec):** define estimands and proxies. **No ILP changes.**

**Phase 1 (E037 pre-registered):** descriptive **scoring** only.

For each GW in the frozen E024 stack, after squads are chosen:

1. Compute \(V_A(S)\), \(V_B(S)\) on control and treat squads (same μ, same XI solve rules).
2. Record realized \(R_{\text{Cap}}\) and ΔCap.
3. Compare **alignment** of \(\Delta V_A\), \(\Delta V_B\) with ΔCap on FAIL vs PASS.

**Primary (pre-registered):**

\[
\text{corr}(\Delta V_B,\, \Delta R) \quad \text{vs} \quad \text{corr}(\Delta V_A,\, \Delta R)
\]

on FAIL-season GWs (gate from E024), treatment arm.

**Secondary (report only):**

- Same on PASS seasons (architecture-intrinsic)
- GW-level AUROC: does \(\Delta V\) predict portfolio_bad?
- Stratify by g_treat bucket (small vs large displacement)

**Forbidden in E037:**

- Changing which squad the ILP picks
- Fitting weights on FAIL and testing on FAIL
- Promoting \(V_B\) because it wins on one season
- Implementing \(V_C\) without state spec

**Branching (after E037):**

| Result | Next step |
|---|---|
| \(V_B\) aligns better than \(V_A\) on FAIL | Pre-register **E038**: squad ILP with `objective=horizon` under frozen μ only |
| Neither aligns | Estimand may need C (state) or non-separable D; spec C state vector |
| \(V_B\) helps PASS only | Horizon mismatch artifact; revisit production vs harness objectives |
| Both anti-align on FAIL | Irreducible μ-regime problem; upstream revisit, not \(V\) tweak |

---

## 9. Failure modes to preserve in any new \(V(S)\)

1. **Regime anti-alignment** (E030): FAIL corr(ΔU, ΔCap) < 0
2. **μ inversion** (E032): better μ, worse realization on FAIL
3. **Tripwire re-equilibration** (E034b): single entrant → full 15 jump
4. **Objective gap** (E034c/E035): G_treat explains jump under treat μ
5. **Separability collapse** (E036): additive \(V\) ⇒ MC ≡ U

Any proposed \(V(S)\) must state how it addresses (or accepts) each.

---

## 10. Formal integrity note

[`FORMAL.md`](FORMAL.md) separates **horizon**, **objective U**, and **scoring g**.
A new \(V(S)\) is a change to **objective U**, not to the feasible set F.

`V1_GW1` (E007) is a valid pattern: same μ, different U (`next` vs `horizon`).
E037–E038 must follow that pattern — **never** change μ and \(V\) simultaneously.

Lean modules do not yet formalize squad/XI legality or \(V(S)\). When \(V\) is frozen,
add a declaration to `formal/` before production integration.

---

## 11. Forbidden next steps

- Another admission score under same \(U\) (E036 closed)
- MC integration (H-MC1 Phase C closed)
- Packaging dose, ε, λ fishing on FAIL panel
- Setting \(V(S) =\) realized Cap predictor without out-of-sample protocol
- Combining A+B+C into one objective before individual discrimination
- Promoting `rates_v2b` on FAIL evidence

---

## 12. Current research call

```text
PRODUCTION     v2am_s + rates=v1 + fixtures v1  (horizon squad objective)
CLOSED         E024–E036
SPEC           this document (Phase 0)
NEXT           E037 descriptive V_A vs V_B alignment (pre-registered below)
NOT NEXT       optimizer integration without E037 branch
```

See [`LAB_LOG.md`](LAB_LOG.md) § E037 for frozen scope when implemented.
