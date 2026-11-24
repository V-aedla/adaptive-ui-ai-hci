"""Generate a realistic interaction history for a demo user.

Usage:  python simulate.py <user> <novice|expert> [events]

The simulated user follows a habit (Email -> Calendar -> Tasks, Reports ->
Files) with some randomness, so the adaptation engine has patterns to learn.
"""
import random
import sys
import time
from pathlib import Path

from adaptive import UserProfile

HABIT = {
    "email": ["calendar"] * 6 + ["tasks", "chat"],
    "calendar": ["tasks"] * 5 + ["email", "notes"],
    "tasks": ["email"] * 3 + ["reports", "notes", "email"],
    "reports": ["files"] * 5 + ["email"],
    "files": ["email", "reports", "notes"],
    "notes": ["email", "tasks"],
    "chat": ["email", "tasks"],
    "settings": ["email"],
}


def simulate(user: str, level: str, n: int = 60, seed: int = 7) -> Path:
    rng = random.Random(seed)
    path = Path(__file__).parent / "data" / f"{user}.json"
    p = UserProfile(user=user)
    ts = time.time() - n * (2.5 if level == "expert" else 9)
    cur = "email"
    for _ in range(n):
        gap = rng.uniform(1.0, 3.5) if level == "expert" else rng.uniform(4, 14)
        ts += gap
        err = rng.random() < (0.03 if level == "expert" else 0.25)
        p.record(cur, error=err, ts=ts)
        cur = rng.choice(HABIT[cur])
    p.save(path)
    return path


if __name__ == "__main__":
    u = sys.argv[1] if len(sys.argv) > 1 else "demo"
    lvl = sys.argv[2] if len(sys.argv) > 2 else "expert"
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    print("wrote", simulate(u, lvl, n))
