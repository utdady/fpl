# FPL V1

Projection-first Fantasy Premier League squad picker for 2026/27.

The projection engine is the brain. The ILP optimizer is the decision layer.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
python fpl.py --horizon 6 --strategy balanced
```

Strategies: `safe`, `balanced`, `aggressive`.

Interrogate a squad without changing the model:

```bash
python -m engine.audit --strategy balanced
```

Live data comes from the official FPL API (timestamped cache in `.cache/fpl`). Historical dumps are not used in V1.
