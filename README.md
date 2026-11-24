# AdaptiveDesk — AI-Based Adaptive User Interface

A small Flask web app that adapts its own interface at runtime from how each user
interacts with it. Built for the *Adaptive UI using AI/HCI* project.

**GitHub repository:** https://github.com/YOUR-USERNAME/adaptive-ui-ai-hci  *(replace after pushing)*

## What adapts

| Adaptation | Technique | Where |
|---|---|---|
| Tile order ("most used" first) | Frequency + recency score with 1-day half-life and a 15 % stability margin so the layout does not reshuffle on small changes | `adaptive/engine.py` → `update_layout()` |
| "Suggested next" banner | scikit-learn `CategoricalNB` trained on (previous tool, time of day) → next tool | `predict_next()` |
| Novice vs expert mode | Mis-selection rate (opened a tool and pressed Back within 1.5 s) and average time between actions | `expertise()` |
| Transparency & control | "Why does my screen look like this?" panel, Pause adaptation, Reset learning | `view()`, `/api/freeze`, `/api/reset` |

## Run it

```bash
pip install -r requirements.txt
python simulate.py alex expert 60      # optional: seed a demo user
python simulate.py learner novice 30
python app.py                          # open http://127.0.0.1:5000
```

Type a user name (e.g. `alex`, `learner`, or a new name) in the header to switch profiles.
Click tiles to use the app; the layout, suggestion and mode update after every visit to the desk.
Expert users can press the letter keys shown on the tiles (E, C, T …) and Esc to go back.

## Tests

```bash
python -m pytest -q
```

## Project structure

```
app.py                 Flask routes (UI + JSON API)
adaptive/engine.py     Adaptation engine (layout, prediction, expertise, explanations)
templates/index.html   Page markup
static/app.js          Front end: renders the adapted view, logs interactions
static/style.css       Styles, including compact "expert" mode
simulate.py            Generates realistic interaction histories for demos
tests/test_engine.py   Unit and API tests (pytest)
data/                  Per-user interaction logs (JSON)
```


## Libraries

Flask 3.1 (BSD-3), scikit-learn 1.9 (BSD-3), NumPy 2.x (BSD-3).
