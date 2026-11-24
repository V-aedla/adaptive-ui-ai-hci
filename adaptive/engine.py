"""
AdaptiveDesk - adaptation engine.

Three adaptive behaviours are driven from the user's own interaction log:

1. Adaptive layout     - tiles are ranked by a frequency + recency score.
                         A stability threshold stops the layout from
                         reshuffling on small score changes (a conservative
                         policy, after Todi et al., 2021).
2. Next-action model   - a scikit-learn Categorical Naive Bayes classifier
                         predicts the user's next tool from the previous tool
                         and the time of day, and is shown as a suggestion.
3. Expertise detection - the user's mis-click rate and average time between
                         actions classify them as "novice" or "expert";
                         novices get large tiles and help text, experts get a
                         compact grid with keyboard shortcuts.

Every adaptation produces a plain-language explanation so the user can see
why the interface changed, and the user can reset or freeze adaptation.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.naive_bayes import CategoricalNB

TOOLS = [
    {"id": "email", "name": "Email", "icon": "✉", "key": "E", "help": "Read and send messages."},
    {"id": "calendar", "name": "Calendar", "icon": "📅", "key": "C", "help": "See meetings and deadlines."},
    {"id": "tasks", "name": "Tasks", "icon": "✔", "key": "T", "help": "Track your to-do list."},
    {"id": "notes", "name": "Notes", "icon": "📝", "key": "N", "help": "Write quick notes."},
    {"id": "files", "name": "Files", "icon": "📁", "key": "F", "help": "Browse shared documents."},
    {"id": "reports", "name": "Reports", "icon": "📊", "key": "R", "help": "View weekly analytics."},
    {"id": "chat", "name": "Team Chat", "icon": "💬", "key": "H", "help": "Message your team."},
    {"id": "settings", "name": "Settings", "icon": "⚙", "key": "S", "help": "Change preferences."},
]
TOOL_IDS = [t["id"] for t in TOOLS]
TOOL_INDEX = {t: i for i, t in enumerate(TOOL_IDS)}

# Tunable parameters
RECENCY_HALF_LIFE_S = 60 * 60 * 24      # one day
STABILITY_MARGIN = 0.15                 # min relative score gain before two tiles swap
MIN_SAMPLES_FOR_MODEL = 6
EXPERT_MAX_ERROR_RATE = 0.10
EXPERT_MAX_GAP_S = 4.0
MIN_EVENTS_FOR_EXPERTISE = 10


def hour_bucket(ts: float) -> int:
    """0 = morning (05-12), 1 = afternoon (12-17), 2 = evening/night."""
    h = time.localtime(ts).tm_hour
    if 5 <= h < 12:
        return 0
    if 12 <= h < 17:
        return 1
    return 2


@dataclass
class UserProfile:
    user: str
    events: list = field(default_factory=list)      # {"tool", "ts", "error"}
    layout: list = field(default_factory=lambda: list(TOOL_IDS))
    frozen: bool = False

    # ---------- persistence ----------
    @classmethod
    def load(cls, path: Path, user: str) -> "UserProfile":
        if path.exists():
            data = json.loads(path.read_text())
            return cls(user=user, events=data.get("events", []),
                       layout=data.get("layout", list(TOOL_IDS)),
                       frozen=data.get("frozen", False))
        return cls(user=user)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"events": self.events, "layout": self.layout,
                                    "frozen": self.frozen}, indent=1))

    # ---------- logging ----------
    def record(self, tool: str, error: bool = False, ts: float | None = None) -> None:
        if tool not in TOOL_INDEX:
            raise ValueError(f"unknown tool {tool}")
        self.events.append({"tool": tool, "ts": ts or time.time(), "error": bool(error)})

    @property
    def successful(self) -> list:
        return [e for e in self.events if not e["error"]]


class AdaptationEngine:
    """Turns a UserProfile into an adapted UI description."""

    def __init__(self, profile: UserProfile, now: float | None = None):
        self.p = profile
        self.now = now or time.time()

    # 1. Adaptive layout -------------------------------------------------
    def scores(self) -> dict:
        s = {t: 0.0 for t in TOOL_IDS}
        for e in self.p.successful:
            age = max(0.0, self.now - e["ts"])
            s[e["tool"]] += math.pow(0.5, age / RECENCY_HALF_LIFE_S)
        return s

    def update_layout(self) -> list:
        """Insertion sort that only moves a tile above another when its score
        is clearly higher - this keeps the layout stable and predictable."""
        if self.p.frozen:
            return self.p.layout
        s = self.scores()
        layout = list(self.p.layout)
        changed = True
        while changed:
            changed = False
            for i in range(len(layout) - 1):
                a, b = layout[i], layout[i + 1]
                if s[b] > s[a] * (1 + STABILITY_MARGIN) + 0.01:
                    layout[i], layout[i + 1] = b, a
                    changed = True
        self.p.layout = layout
        return layout

    # 2. Next-action prediction -----------------------------------------
    def training_data(self):
        ev = self.p.successful
        X, y = [], []
        for prev, nxt in zip(ev, ev[1:]):
            X.append([TOOL_INDEX[prev["tool"]], hour_bucket(nxt["ts"])])
            y.append(TOOL_INDEX[nxt["tool"]])
        return np.array(X), np.array(y)

    def predict_next(self) -> dict | None:
        ev = self.p.successful
        X, y = self.training_data()
        if len(y) < MIN_SAMPLES_FOR_MODEL or len(set(y)) < 2:
            return None
        model = CategoricalNB(alpha=1.0, min_categories=[len(TOOL_IDS), 3])
        model.fit(X, y)
        last = ev[-1]["tool"]
        query = np.array([[TOOL_INDEX[last], hour_bucket(self.now)]])
        proba = model.predict_proba(query)[0]
        order = np.argsort(proba)[::-1]
        best = int(model.classes_[order[0]])
        return {
            "tool": TOOL_IDS[best],
            "confidence": round(float(proba[order[0]]), 2),
            "after": last,
            "samples": int(len(y)),
        }

    # 3. Expertise detection -------------------------------------------
    def expertise(self) -> dict:
        ev = self.p.events[-30:]
        if len(ev) < MIN_EVENTS_FOR_EXPERTISE:
            return {"level": "novice", "error_rate": None, "avg_gap": None,
                    "reason": "Not enough interactions yet, so help text is shown."}
        err = sum(e["error"] for e in ev) / len(ev)
        gaps = [b["ts"] - a["ts"] for a, b in zip(ev, ev[1:])]
        gaps = [g for g in gaps if g < 60]          # ignore idle breaks
        avg_gap = sum(gaps) / len(gaps) if gaps else 99.0
        expert = err <= EXPERT_MAX_ERROR_RATE and avg_gap <= EXPERT_MAX_GAP_S
        return {
            "level": "expert" if expert else "novice",
            "error_rate": round(err, 2),
            "avg_gap": round(avg_gap, 1),
            "reason": (f"Error rate {err:.0%} and {avg_gap:.1f}s between actions: "
                       + ("compact mode with shortcuts enabled." if expert
                          else "larger tiles and help text kept on.")),
        }

    # Combined view model ----------------------------------------------
    def view(self) -> dict:
        before = list(self.p.layout)
        layout = self.update_layout()
        moved = [t for i, t in enumerate(layout) if before.index(t) != i]
        s = self.scores()
        pred = self.predict_next()
        exp = self.expertise()
        explanations = []
        if self.p.frozen:
            explanations.append("Layout adaptation is paused - tiles keep their current order.")
        elif s[layout[0]] > 0:
            explanations.append(f"{name(layout[0])} is first because you use it most often recently.")
        if moved and not self.p.frozen:
            explanations.append("Tiles moved this visit: " + ", ".join(name(t) for t in moved) + ".")
        if pred:
            explanations.append(f"After {name(pred['after'])} you usually open {name(pred['tool'])} "
                                f"({int(pred['confidence'] * 100)}% confidence, {pred['samples']} examples).")
        explanations.append(exp["reason"])
        return {
            "layout": [tool(t) | {"score": round(s[t], 2)} for t in layout],
            "prediction": pred,
            "expertise": exp,
            "explanations": explanations,
            "frozen": self.p.frozen,
            "event_count": len(self.p.events),
        }


def tool(tid: str) -> dict:
    return dict(next(t for t in TOOLS if t["id"] == tid))


def name(tid: str) -> str:
    return tool(tid)["name"]
