import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptive.engine import TOOL_IDS, AdaptationEngine, UserProfile  # noqa: E402


def make(seq, gap=2.0, errors=()):
    p = UserProfile(user="t")
    ts = time.time() - len(seq) * gap
    for i, t in enumerate(seq):
        ts += gap
        p.record(t, error=i in errors, ts=ts)
    return p


def test_default_layout_when_no_history():
    v = AdaptationEngine(UserProfile(user="t")).view()
    assert [t["id"] for t in v["layout"]] == TOOL_IDS
    assert v["prediction"] is None
    assert v["expertise"]["level"] == "novice"


def test_frequent_tool_moves_to_top():
    p = make(["reports"] * 8 + ["email"])
    v = AdaptationEngine(p).view()
    assert v["layout"][0]["id"] == "reports"


def test_stability_margin_prevents_small_swaps():
    p = make(["email", "calendar", "calendar"])  # small difference after equal use
    p2 = make(["email", "calendar"])             # equal use -> no change
    assert AdaptationEngine(p2).update_layout()[:2] == ["email", "calendar"]
    assert AdaptationEngine(p).update_layout()[0] == "calendar"


def test_predicts_habitual_next_tool():
    p = make(["email", "calendar", "tasks"] * 6 + ["email"])
    pred = AdaptationEngine(p).predict_next()
    assert pred["tool"] == "calendar"
    assert pred["confidence"] > 0.5


def test_expertise_detection():
    fast = make(["email", "tasks"] * 8, gap=1.5)
    slow = make(["email", "tasks"] * 8, gap=8, errors={1, 4, 7, 10})
    assert AdaptationEngine(fast).expertise()["level"] == "expert"
    assert AdaptationEngine(slow).expertise()["level"] == "novice"


def test_frozen_layout_does_not_change():
    p = make(["reports"] * 8)
    p.frozen = True
    assert AdaptationEngine(p).update_layout() == TOOL_IDS


def test_flask_api(tmp_path, monkeypatch):
    import app as webapp
    monkeypatch.setattr(webapp, "DATA_DIR", tmp_path)
    c = webapp.app.test_client()
    for _ in range(5):
        assert c.post("/api/event", json={"user": "x", "tool": "notes"}).status_code == 200
    data = c.get("/api/ui?user=x").get_json()
    assert data["layout"][0]["id"] == "notes"
    assert c.post("/api/event", json={"user": "x", "tool": "bogus"}).status_code == 400
