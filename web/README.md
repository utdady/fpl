# FPL research viewer

Read-only UI over the frozen records in `../records/`. It never writes to them.

## Running

```bash
python ../scripts/export_ui.py   # regenerate public/data from records/ + .cache/fpl
npm install
npm run dev
```

Re-run the export whenever the engine produces new records. `public/data/` is
committed as a versioned artifact so Vercel builds need only Node.

## Deploying

Not deployed yet. When it is, two settings are not optional:

1. **Root Directory must be `web`.** The Next app is a subdirectory of the research
   repo. This cannot be set from `vercel.json`; it lives in the Vercel project
   settings. Without it the build finds no framework and every route 404s.
2. **`outputFileTracingIncludes` must stay in `next.config.mjs`.** Every page is
   prerendered except the live-season notices, which render on demand and read the
   manifest through a computed path that file tracing cannot follow. Removing the
   entry gives two routes that pass `next start` locally and throw ENOENT in
   production.

Re-running `export_ui.py` refreshes the FPL snapshot fields. Do not do it to make
the display look current: `.cache/fpl/` is gitignored and holds the only copy of
the snapshot the GW1 audit was computed against.

## Data layer

| Tier | Source | Contents |
|---|---|---|
| A | `records/**/*.csv` | mu, sigma, p_start, P(10+), actuals, evaluation metrics, XI membership |
| B | `.cache/fpl/*.json` | names, prices, ownership, availability, fixtures, FDR, `ep_next` |
| C | `/api/fpl/*` proxy | in-play points, price moves, a manager's own squad |

Tier C exists because the FPL API sends no `Access-Control-Allow-Origin` header
and cannot be called from the browser. The route allowlists specific endpoints
and sets a revalidate window on each so viewers share one upstream fetch.

## Surfaces

- `/` — live prediction pool. No eleven: `capture.py` does not persist squad
  selection, and the frozen fifteen was solved on a six-gameweek horizon utility
  the record does not store.
- `/squad/[season]/[gw]` — the V1 eleven beside the B0 eleven and the oracle.
  An eleven, not a fifteen: `decision_decomp.csv` holds no bench.
- `/lab/[season]` — evaluation panels, all reproducing values in
  `docs/LAB_LOG.md`.
- `/audit` — the six fields that must be persisted before this surface exists.

## Colour law

Every chart obeys it, so a reader never has to ask whether a number is a
prediction or an outcome.

| Colour | Meaning |
|---|---|
| cyan | V1 model output |
| green | realized points and minutes |
| magenta | blanks, zero-minute slots, leakage flags |
| violet | Vaastav xP (B0), not our model |
| amber | god-mode hindsight oracle |

## Honesty constraints

These are load-bearing, not decoration:

- Caveat strings live in the exported JSON, not in components, so a chart cannot
  reach the page without the warning its source data carries.
- Every `p_start` is shown beside the actual start rate observed at that
  confidence across four seasons (E013: 75-78% at a claimed 0.90+).
- B0 is drawn in its own colour and its flagged weeks are shaded. It is an
  upper-bound diagnostic, never a baseline or a ceiling.
- The regret oracle is named in the chart subtitle.
- Any FPL availability figure carries the snapshot date beside it. Availability and
  news move daily, so an undated percentage from a days-old capture reads as
  current when it is not.
- No outcome distribution is drawn from mu and sigma alone. FPL points are lumpy
  and a bell curve would assert a shape the model never claimed.
