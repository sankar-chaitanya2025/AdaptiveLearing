"""
scripts/seed_study.py
Stage 12 — Seed the 10 fixed study test-set problems.

Problem set design:
  5 Easy  (difficulty < 0.35) — Arrays × 2, Hash Maps × 2, Recursion × 1
  3 Medium (difficulty 0.35–0.74) — Arrays × 1, Hash Maps × 1, Recursion × 1
  2 Hard  (difficulty ≥ 0.75) — Arrays × 1, Recursion × 1

All problems are marked is_study_only=True and are therefore excluded from
the practice/generator paths (Brain B, Plato, get_problems()).

Each problem ships with 3 visible tests and 5 hidden tests to give a
meaningful score distribution across trials.

Usage (inside the backend container or with local venv):
    python scripts/seed_study.py

Safe to re-run — skips problems that already exist (by title match).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal
from models.problem import Problem, CreatedBy


# ---------------------------------------------------------------------------
# The 10 fixed study problems
# ---------------------------------------------------------------------------

STUDY_PROBLEMS = [

    # ── EASY ─────────────────────────────────────────────────────────────────

    {
        "title": "Find Max in Array",
        "topic": "arrays",
        "difficulty": 0.15,
        "statement": (
            "## Find Maximum Element\n\n"
            "Given a list of integers `nums`, return the largest element.\n\n"
            "### Constraints\n- `1 ≤ len(nums) ≤ 10^4`\n- `-10^9 ≤ nums[i] ≤ 10^9`\n\n"
            "### Example\n```\nInput:  nums = [3, 1, 4, 1, 5, 9, 2]\nOutput: 9\n```"
        ),
        "visible_tests": [
            {"input": "[3, 1, 4, 1, 5, 9, 2]",  "expected": "9"},
            {"input": "[-3, -1, -4]",            "expected": "-1"},
            {"input": "[42]",                    "expected": "42"},
        ],
        "hidden_tests": [
            {"input": "[0, 0, 0]",               "expected": "0"},
            {"input": "[1000000000]",             "expected": "1000000000"},
            {"input": "[-1000000000, 999999999]", "expected": "999999999"},
            {"input": "[5, 5, 5, 5]",            "expected": "5"},
            {"input": "[1, 2, 3, 4, 5]",         "expected": "5"},
        ],
        "prerequisite_topics": [],
    },

    {
        "title": "Reverse an Array",
        "topic": "arrays",
        "difficulty": 0.18,
        "statement": (
            "## Reverse Array\n\n"
            "Given a list `nums`, return a new list with elements in reverse order.\n\n"
            "### Example\n```\nInput:  nums = [1, 2, 3, 4]\nOutput: [4, 3, 2, 1]\n```"
        ),
        "visible_tests": [
            {"input": "[1, 2, 3, 4]",  "expected": "[4, 3, 2, 1]"},
            {"input": "[5]",           "expected": "[5]"},
            {"input": "[]",            "expected": "[]"},
        ],
        "hidden_tests": [
            {"input": "[1, 1, 1]",     "expected": "[1, 1, 1]"},
            {"input": "[2, 3]",        "expected": "[3, 2]"},
            {"input": "[9, 8, 7, 6]",  "expected": "[6, 7, 8, 9]"},
            {"input": "[-1, 0, 1]",    "expected": "[1, 0, -1]"},
            {"input": "[10, 20, 30]",  "expected": "[30, 20, 10]"},
        ],
        "prerequisite_topics": [],
    },

    {
        "title": "Count Character Frequency",
        "topic": "hash_maps",
        "difficulty": 0.22,
        "statement": (
            "## Character Frequency Map\n\n"
            "Given a string `s`, return a dictionary mapping each character to "
            "the number of times it appears.\n\n"
            "### Example\n```\nInput:  s = 'aab'\nOutput: {'a': 2, 'b': 1}\n```\n\n"
            "Return the dict — order does not matter."
        ),
        "visible_tests": [
            {"input": "'aab'",    "expected": "{'a': 2, 'b': 1}"},
            {"input": "'abc'",    "expected": "{'a': 1, 'b': 1, 'c': 1}"},
            {"input": "''",       "expected": "{}"},
        ],
        "hidden_tests": [
            {"input": "'aaaa'",   "expected": "{'a': 4}"},
            {"input": "'aabb'",   "expected": "{'a': 2, 'b': 2}"},
            {"input": "'hello'",  "expected": "{'h': 1, 'e': 1, 'l': 2, 'o': 1}"},
            {"input": "'zzzz'",   "expected": "{'z': 4}"},
            {"input": "'ab'",     "expected": "{'a': 1, 'b': 1}"},
        ],
        "prerequisite_topics": [],
    },

    {
        "title": "Two Sum (Classic)",
        "topic": "hash_maps",
        "difficulty": 0.28,
        "statement": (
            "## Two Sum\n\n"
            "Given a list of integers `nums` and an integer `target`, return the "
            "**indices** of the two numbers that add up to `target`.\n\n"
            "Exactly one solution exists. Each element may only be used once.\n\n"
            "### Example\n```\nInput:  nums = [2, 7, 11, 15], target = 9\nOutput: [0, 1]\n```"
        ),
        "visible_tests": [
            {"input": "[2, 7, 11, 15], 9",   "expected": "[0, 1]"},
            {"input": "[3, 2, 4], 6",        "expected": "[1, 2]"},
            {"input": "[3, 3], 6",           "expected": "[0, 1]"},
        ],
        "hidden_tests": [
            {"input": "[1, 2, 3, 4], 7",     "expected": "[2, 3]"},
            {"input": "[0, 4, 3, 0], 0",     "expected": "[0, 3]"},
            {"input": "[-3, 4, 3, 90], 0",   "expected": "[0, 2]"},
            {"input": "[2, 5, 5, 11], 10",   "expected": "[1, 2]"},
            {"input": "[1, 9], 10",          "expected": "[0, 1]"},
        ],
        "prerequisite_topics": [],
    },

    {
        "title": "Factorial",
        "topic": "recursion",
        "difficulty": 0.25,
        "statement": (
            "## Factorial\n\n"
            "Write a **recursive** function that returns `n!` for a non-negative integer `n`.\n\n"
            "Recall: `0! = 1`, `n! = n × (n-1)!`\n\n"
            "### Example\n```\nInput:  n = 5\nOutput: 120\n```"
        ),
        "visible_tests": [
            {"input": "5",   "expected": "120"},
            {"input": "0",   "expected": "1"},
            {"input": "1",   "expected": "1"},
        ],
        "hidden_tests": [
            {"input": "3",   "expected": "6"},
            {"input": "4",   "expected": "24"},
            {"input": "6",   "expected": "720"},
            {"input": "7",   "expected": "5040"},
            {"input": "10",  "expected": "3628800"},
        ],
        "prerequisite_topics": [],
    },

    # ── MEDIUM ────────────────────────────────────────────────────────────────

    {
        "title": "Subarray Sum Equals K",
        "topic": "arrays",
        "difficulty": 0.52,
        "statement": (
            "## Subarray Sum Equals K\n\n"
            "Given an array of integers `nums` and an integer `k`, return the "
            "total number of **contiguous subarrays** whose elements sum to `k`.\n\n"
            "### Constraints\n- `1 ≤ len(nums) ≤ 2×10^4`\n- `-1000 ≤ nums[i] ≤ 1000`\n\n"
            "### Example\n```\nInput:  nums = [1, 1, 1], k = 2\nOutput: 2\n```"
        ),
        "visible_tests": [
            {"input": "[1, 1, 1], 2",      "expected": "2"},
            {"input": "[1, 2, 3], 3",      "expected": "2"},
            {"input": "[0, 0, 0], 0",      "expected": "6"},
        ],
        "hidden_tests": [
            {"input": "[1], 1",            "expected": "1"},
            {"input": "[-1, -1, 1], 0",    "expected": "1"},
            {"input": "[3, 4, 7, 2, -3], 7", "expected": "4"},
            {"input": "[1, 2, 1, 2], 3",  "expected": "2"},
            {"input": "[1, -1, 1, -1], 0","expected": "4"},
        ],
        "prerequisite_topics": ["arrays"],
    },

    {
        "title": "Group Anagrams",
        "topic": "hash_maps",
        "difficulty": 0.55,
        "statement": (
            "## Group Anagrams\n\n"
            "Given a list of strings `strs`, group the anagrams together and return a "
            "**sorted** list of groups (each group sorted internally).\n\n"
            "### Example\n```\nInput:  strs = ['eat','tea','tan','ate','nat','bat']\n"
            "Output: [['ate','eat','tea'], ['bat'], ['nat','tan']]\n```"
        ),
        "visible_tests": [
            {"input": "['eat','tea','tan','ate','nat','bat']",
             "expected": "[['ate', 'eat', 'tea'], ['bat'], ['nat', 'tan']]"},
            {"input": "['']",
             "expected": "[['']]"},
            {"input": "['a']",
             "expected": "[['a']]"},
        ],
        "hidden_tests": [
            {"input": "['abc','bca','cab']",
             "expected": "[['abc', 'bca', 'cab']]"},
            {"input": "['ab','ba','cd','dc']",
             "expected": "[['ab', 'ba'], ['cd', 'dc']]"},
            {"input": "['x','y','z']",
             "expected": "[['x'], ['y'], ['z']]"},
            {"input": "['aa','a']",
             "expected": "[['a'], ['aa']]"},
            {"input": "['listen','silent','enlist']",
             "expected": "[['enlist', 'listen', 'silent']]"},
        ],
        "prerequisite_topics": ["hash_maps"],
    },

    {
        "title": "Power Function",
        "topic": "recursion",
        "difficulty": 0.48,
        "statement": (
            "## Power Function\n\n"
            "Implement `solution(x, n)` that computes `x^n` **recursively**.\n"
            "You may assume `n` is a non-negative integer and `x` is an integer.\n\n"
            "### Example\n```\nInput:  x = 2, n = 10\nOutput: 1024\n```"
        ),
        "visible_tests": [
            {"input": "2, 10",   "expected": "1024"},
            {"input": "3, 0",    "expected": "1"},
            {"input": "5, 1",    "expected": "5"},
        ],
        "hidden_tests": [
            {"input": "2, 0",    "expected": "1"},
            {"input": "10, 3",   "expected": "1000"},
            {"input": "7, 2",    "expected": "49"},
            {"input": "1, 100",  "expected": "1"},
            {"input": "0, 5",    "expected": "0"},
        ],
        "prerequisite_topics": ["recursion"],
    },

    # ── HARD ──────────────────────────────────────────────────────────────────

    {
        "title": "Longest Consecutive Sequence",
        "topic": "arrays",
        "difficulty": 0.78,
        "statement": (
            "## Longest Consecutive Sequence\n\n"
            "Given an **unsorted** array of integers `nums`, return the length of "
            "the longest consecutive elements sequence.\n\n"
            "Must run in **O(n)** time.\n\n"
            "### Example\n```\nInput:  nums = [100, 4, 200, 1, 3, 2]\nOutput: 4   # [1, 2, 3, 4]\n```"
        ),
        "visible_tests": [
            {"input": "[100, 4, 200, 1, 3, 2]",   "expected": "4"},
            {"input": "[0, 3, 7, 2, 5, 8, 4, 6, 0, 1]", "expected": "9"},
            {"input": "[]",                        "expected": "0"},
        ],
        "hidden_tests": [
            {"input": "[1]",                       "expected": "1"},
            {"input": "[1, 2, 0, 1]",              "expected": "3"},
            {"input": "[9, 1, 4, 7, 3, 2]",        "expected": "4"},
            {"input": "[0]",                       "expected": "1"},
            {"input": "[1, 3, 5, 7]",              "expected": "1"},
        ],
        "prerequisite_topics": ["arrays", "hash_maps"],
    },

    {
        "title": "Flatten Nested List",
        "topic": "recursion",
        "difficulty": 0.80,
        "statement": (
            "## Flatten Nested List\n\n"
            "Write a **recursive** function that takes a nested list and returns "
            "a flat list of all integers.\n\n"
            "### Example\n"
            "```\nInput:  lst = [1, [2, [3, 4], 5], 6]\nOutput: [1, 2, 3, 4, 5, 6]\n```"
        ),
        "visible_tests": [
            {"input": "[1, [2, [3, 4], 5], 6]",    "expected": "[1, 2, 3, 4, 5, 6]"},
            {"input": "[]",                         "expected": "[]"},
            {"input": "[1, 2, 3]",                  "expected": "[1, 2, 3]"},
        ],
        "hidden_tests": [
            {"input": "[[1, 2], [3, 4]]",           "expected": "[1, 2, 3, 4]"},
            {"input": "[[[1]]]",                    "expected": "[1]"},
            {"input": "[1, [2, [3, [4, [5]]]]]",    "expected": "[1, 2, 3, 4, 5]"},
            {"input": "[[]]",                       "expected": "[]"},
            {"input": "[0, [0, 0], 0]",             "expected": "[0, 0, 0, 0]"},
        ],
        "prerequisite_topics": ["recursion"],
    },
]


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

def seed():
    db = SessionLocal()
    try:
        inserted = 0
        skipped  = 0

        for p in STUDY_PROBLEMS:
            existing = db.query(Problem).filter(Problem.title == p["title"]).first()
            if existing:
                # Ensure the flag is set even if the problem was seeded before Stage 12
                if not existing.is_study_only:
                    existing.is_study_only = True
                    db.commit()
                    print(f"  Updated  is_study_only=True: {p['title']}")
                skipped += 1
                continue

            row = Problem(
                title=p["title"],
                topic=p["topic"],
                difficulty=p["difficulty"],
                statement=p["statement"],
                visible_tests=p["visible_tests"],
                hidden_tests=p["hidden_tests"],
                prerequisite_topics=p["prerequisite_topics"],
                created_by=CreatedBy.human,
                is_study_only=True,
            )
            db.add(row)
            inserted += 1
            print(f"  Inserted: {p['title']} [{p['topic']} / difficulty={p['difficulty']:.2f}]")

        db.commit()
        print(f"\nDone — {inserted} inserted, {skipped} skipped.")
    except Exception as exc:
        db.rollback()
        print(f"Error during seeding: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding study problems …")
    seed()
