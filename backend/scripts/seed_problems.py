"""Seed the problems table with 50 curated coding problems.

Usage (inside Docker):
    python scripts/seed_problems.py
"""

import json
import os
import sys

# Ensure the backend root is on sys.path so imports resolve inside /app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal
from models.problem import Problem, CreatedBy


def seed():
    db = SessionLocal()
    try:
        count = db.query(Problem).count()
        if count > 0:
            print(f"Database already has {count} problems — skipping seed.")
            return

        # Load seed data from JSON file
        json_path = os.path.join(os.path.dirname(__file__), "seed_data.json")
        with open(json_path, "r", encoding="utf-8") as f:
            problems = json.load(f)

        for p in problems:
            row = Problem(
                title=p["title"],
                topic=p["topic"],
                difficulty=p["difficulty"],
                statement=p["statement"],
                visible_tests=p["visible_tests"],
                hidden_tests=p["hidden_tests"],
                prerequisite_topics=p["prerequisite_topics"],
                created_by=CreatedBy(p["created_by"]),
            )
            db.add(row)

        db.commit()
        print(f"Successfully seeded {len(problems)} problems.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
