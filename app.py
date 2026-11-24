"""AdaptiveDesk - Flask web app demonstrating an AI-based adaptive UI."""

import re
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from adaptive import AdaptationEngine, UserProfile

DATA_DIR = Path(__file__).parent / "data"
app = Flask(__name__)


def profile_path(user: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", user) or "guest"
    return DATA_DIR / f"{safe}.json"


def load(user: str) -> UserProfile:
    return UserProfile.load(profile_path(user), user)


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/ui")
def ui():
    user = request.args.get("user", "guest")
    p = load(user)
    view = AdaptationEngine(p).view()
    p.save(profile_path(user))
    return jsonify(view)


@app.post("/api/event")
def event():
    body = request.get_json(force=True)
    user = body.get("user", "guest")
    p = load(user)
    # A quick "Back" (< 1.5 s) means the user opened the wrong tool:
    # mark their last event as a mis-selection instead of a real use.
    if body.get("undo") and p.events and p.events[-1]["tool"] == body.get("tool"):
        p.events[-1]["error"] = True
        p.save(profile_path(user))
        return jsonify({"ok": True, "marked_error": True})
    try:
        p.record(body["tool"], error=body.get("error", False))
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    p.save(profile_path(user))
    return jsonify({"ok": True, "events": len(p.events)})


@app.post("/api/freeze")
def freeze():
    body = request.get_json(force=True)
    user = body.get("user", "guest")
    p = load(user)
    p.frozen = bool(body.get("frozen", True))
    p.save(profile_path(user))
    return jsonify({"frozen": p.frozen})


@app.post("/api/reset")
def reset():
    user = request.get_json(force=True).get("user", "guest")
    path = profile_path(user)
    if path.exists():
        path.unlink()
    return jsonify({"reset": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
