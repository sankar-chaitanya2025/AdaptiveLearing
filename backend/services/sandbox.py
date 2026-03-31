import subprocess
import json


def run_code(code: str, test_cases: list, timeout: int = 2) -> dict:
    runner_script = code + f"""

import sys
import json

test_cases = {json.dumps(test_cases)}
results = []
passed = 0

for tc in test_cases:
    inp = tc.get('input', '')
    expected = tc.get('expected', '')
    try:
        _call = f"solution({{inp}})"
        __result = eval(_call)

        ans_str = str(__result)
        ans_repr = repr(__result)
        is_correct = ans_str == str(expected) or ans_repr == str(expected)

        if is_correct: passed += 1
        results.append({{"input": inp, "expected": str(expected), "actual": ans_repr, "passed": is_correct}})
    except Exception as e:
        results.append({{"input": inp, "expected": str(expected), "actual": type(e).__name__ + ": " + str(e), "passed": False}})

score = passed / len(test_cases) if test_cases else 0.0
print(json.dumps({{"score": float(score), "results": results}}))
"""

    try:
        proc = subprocess.run(
            ["python3", "-c", runner_script],
            text=True,
            capture_output=True,
            timeout=timeout
        )

        if proc.stdout:
            try:
                lines = [line for line in proc.stdout.strip().split('\n') if line.strip()]
                return json.loads(lines[-1])
            except Exception:
                return {"score": 0.0, "results": [], "error": "parse error"}

        return {"score": 0.0, "results": [], "error": "no output"}

    except subprocess.TimeoutExpired:
        return {"score": 0.0, "results": [], "error": "timeout"}
    except Exception:
        return {"score": 0.0, "results": [], "error": "docker error"}