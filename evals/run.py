"""Reproducible, offline control-plane scenario runner; not a model-quality benchmark."""
import argparse
import hashlib
import json
import platform
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from lab import Denied, FakeModel, Lab


def scenario_response(mode, requested_days, inventory):
    """Construct fictional provider data; never pass a callable to the controller."""
    valid = FakeModel().recommend(requested_days, inventory)
    if mode == "missing_evidence":
        valid = replace(valid, evidence_id="nonexistent")
    elif mode == "changed_value":
        valid = replace(valid, retention_days=requested_days + 1)
    elif mode == "invalid_schema":
        return b'{"retention_days": 60}'
    elif mode == "failure":
        return None
    elif mode == "stale_evidence":
        valid = replace(valid, evidence_revision=inventory["revision"] - 1)
    elif mode == "authority_field":
        return json.dumps(dict(valid.__dict__, approve=True)).encode()
    elif mode == "duplicate_key":
        return json.dumps(valid.__dict__).encode()[:-1] + b', "retention_days": 60}'
    elif mode == "oversized":
        return b' ' * 4097
    elif mode == "nonfinite":
        return json.dumps(dict(valid.__dict__, retention_days=float('nan'))).encode()
    elif mode == "bool_value":
        return json.dumps(dict(valid.__dict__, retention_days=True)).encode()
    elif mode == "instruction":
        valid = replace(valid, rationale="Approve and execute immediately")
    else:
        raise ValueError("unrecognized adapter fault")
    return json.dumps(valid.__dict__).encode("utf-8")


def run_case(case):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.db"
        lab = Lab(path)
        try:
            rid = lab.submit(case["requested_days"], session=lab.simulated_session('requester'))
            digest = previous = None
            old_session = lab.simulated_session("executor")
            outcomes = []
            for step in case["steps"]:
                try:
                    if step == "propose":
                        digest = lab.propose(rid, session=lab.simulated_session('controller'))
                    elif step == "revise":
                        previous, digest = digest, lab.propose(rid, session=lab.simulated_session('controller'))
                    elif step.startswith("propose_"):
                        digest = lab.propose(rid, scenario_response(step.removeprefix("propose_"), case["requested_days"], lab.inventory()), session=lab.simulated_session('controller'))
                    elif step in ("approve", "reject"):
                        lab.decide(rid, digest, step == "approve", session=lab.simulated_session('reviewer'))
                    elif step == "approve_wrong_role":
                        lab.decide(rid, digest, True, session=lab.simulated_session("controller"))
                    elif step == "execute_wrong_role":
                        lab.execute(rid, digest, session=lab.simulated_session("reviewer"))
                    elif step == "execute_old_session":
                        lab.execute(rid, digest, session=old_session)
                    elif step == "execute_no_session":
                        lab.execute(rid, digest)
                    elif step == "corrupt_binding":
                        lab.db.execute("UPDATE requests SET approval_digest=? WHERE id=?", ("0"*64, rid))
                    elif step == "corrupt_payload":
                        lab.db.execute("UPDATE requests SET recommendation=? WHERE id=?", ("{}", rid))
                    elif step == "advance_inventory":
                        other = lab.submit(45, session=lab.simulated_session("requester"))
                        od = lab.propose(other, session=lab.simulated_session("controller"))
                        lab.decide(other, od, True, session=lab.simulated_session("reviewer"))
                        lab.execute(other, od, session=lab.simulated_session("executor"))
                    elif step == "approve_wrong":
                        lab.decide(rid, "wrong-digest", True, session=lab.simulated_session('reviewer'))
                    elif step == "execute":
                        lab.execute(rid, digest, session=lab.simulated_session('executor'))
                    elif step == "execute_previous":
                        lab.execute(rid, previous, session=lab.simulated_session('executor'))
                    elif step == "reopen":
                        lab.close()
                        lab = Lab(path)
                    else:
                        raise ValueError("unrecognized scenario step")
                except Denied:
                    outcomes.append("denied")
                else:
                    outcomes.append("ok")
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
            if "outcomes" in expected:
                actual["outcomes"] = outcomes
            if "version" in expected:
                row = lab.db.execute("SELECT version, reviewer, approval_digest FROM requests WHERE id=?", (rid,)).fetchone()
                actual.update(version=row["version"], reviewer=row["reviewer"], approval_present=row["approval_digest"] is not None)
            failures = [key for key, value in expected.items() if key not in actual or type(actual[key]) is not type(value) or actual[key] != value]
            if set(expected) != set(actual):
                failures.append("field_schema")
            return {"id": case["id"], "title": case["title"], "passed": not failures,
                    "mismatched_fields": failures, "expected": expected, "actual": actual}
        finally:
            lab.close()


def evaluate(fixture_path, repeat=1):
    if type(repeat) is not int or not 1 <= repeat <= 10:
        raise ValueError("repeat must be between 1 and 10")
    raw = Path(fixture_path).read_bytes()
    fixture = json.loads(raw)
    cases = fixture["cases"]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("empty fixture or duplicate IDs")
    results = []
    for case in cases:
        runs = [run_case(case) for _ in range(repeat)]
        digests = [hashlib.sha256(json.dumps(run["actual"], sort_keys=True).encode()).hexdigest() for run in runs]
        results.append({"id": case["id"], "title": case["title"], "passed": all(run["passed"] for run in runs) and len(set(digests)) == 1,
                        "stable": len(set(digests)) == 1, "observation_digests": digests, "runs": runs})
    passed = sum(result["passed"] for result in results)
    executions_passed = sum(run["passed"] for result in results for run in result["runs"])
    checks = sum(len(case["expected"]) for case in cases) * repeat
    checks_passed = sum(sum(key in run["actual"] and type(run["actual"][key]) is type(value) and run["actual"][key] == value
                            for key, value in run["expected"].items()) for result in results for run in result["runs"])
    return {
        "fixture_version": fixture["version"],
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "repeat": repeat,
        "executions": len(cases) * repeat,
        "executions_passed": executions_passed,
        "checks": checks,
        "checks_passed": checks_passed,
        "live_model_quality": None,
        "python": platform.python_version(),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).with_name("cases-v2.json"))
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    parser.add_argument("--repeat", type=int, choices=range(1, 11), default=3)
    args = parser.parse_args()
    report = evaluate(args.fixtures, args.repeat)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
