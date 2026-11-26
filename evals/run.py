"""Reproducible, offline control-plane scenario runner; not a model-quality benchmark."""
import argparse
import json
import platform
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from lab import Denied, FakeModel, Lab


class ScenarioAdapter:
    """Controlled fake-provider faults, not real prompt-injection attempts."""

    def __init__(self, mode):
        self.mode = mode

    def recommend(self, requested_days, inventory):
        valid = FakeModel().recommend(requested_days, inventory)
        if self.mode == "missing_evidence":
            return replace(valid, evidence_id="nonexistent")
        if self.mode == "changed_value":
            return replace(valid, retention_days=requested_days + 1)
        if self.mode == "invalid_schema":
            return {"retention_days": requested_days}
        if self.mode == "failure":
            raise RuntimeError("synthetic adapter failure")
        if self.mode == "stale_evidence":
            return replace(valid, evidence_revision=inventory["revision"] - 1)
        raise ValueError("unrecognized adapter fault")


def run_case(case):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.db"
        lab = Lab(path)
        try:
            rid = lab.submit(case["requested_days"])
            digest = previous = None
            for step in case["steps"]:
                try:
                    if step == "propose":
                        digest = lab.propose(rid)
                    elif step == "revise":
                        previous, digest = digest, lab.propose(rid)
                    elif step.startswith("propose_"):
                        digest = lab.propose(rid, ScenarioAdapter(step.removeprefix("propose_")))
                    elif step in ("approve", "reject"):
                        lab.decide(rid, digest, "synthetic-reviewer", step == "approve")
                    elif step == "approve_wrong":
                        lab.decide(rid, "wrong-digest", "synthetic-reviewer", True)
                    elif step == "execute":
                        lab.execute(rid, digest)
                    elif step == "execute_previous":
                        lab.execute(rid, previous)
                    elif step == "reopen":
                        lab.close()
                        lab = Lab(path)
                    else:
                        raise ValueError("unrecognized scenario step")
                except Denied:
                    # Continue: later steps may probe whether denial left state intact.
                    pass
            inventory = lab.inventory()
            actual = {
                "days": inventory["days"],
                "revision": inventory["revision"],
                "actions": lab.db.execute("SELECT COUNT(*) FROM actions").fetchone()[0],
                "status": lab.db.execute("SELECT status FROM requests WHERE id=?", (rid,)).fetchone()[0],
                "denials": [d["operation"] for d in lab.denials()],
                "events": [e["kind"] for e in lab.events(rid)],
            }
            expected = case["expected"]
            failures = [key for key, value in expected.items() if actual.get(key) != value]
            if set(expected) != set(actual):
                failures.append("field_schema")
            return {"id": case["id"], "title": case["title"], "passed": not failures,
                    "mismatched_fields": failures, "expected": expected, "actual": actual}
        finally:
            lab.close()


def evaluate(fixture_path):
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    cases = fixture["cases"]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("empty fixture or duplicate IDs")
    results = [run_case(case) for case in cases]
    passed = sum(result["passed"] for result in results)
    return {
        "fixture_version": fixture["version"],
        "python": platform.python_version(),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).with_name("cases-v1.json"))
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    report = evaluate(args.fixtures)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
