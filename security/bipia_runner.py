from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.core.guardrails import filter_selected_sources, inspect_query_input, sanitize_output_text
from api.core.settings import get_settings


def _run_case(case: dict[str, object]) -> dict[str, object]:
    case_id = str(case.get("case_id") or "")
    rail_type = str(case.get("rail_type") or "")
    expect_action = str(case.get("expect_action") or "")
    observed_action = "none"

    if rail_type == "input":
        _query, events, blocked = inspect_query_input(str(case.get("payload") or ""), case_id)
        observed_action = "block" if blocked else (events[0].action_taken if events else "none")
    elif rail_type == "retrieval":
        payload = dict(case.get("payload") or {})
        source = SimpleNamespace(
            title=str(payload.get("title") or ""),
            snippet=str(payload.get("snippet") or ""),
            query=str(payload.get("query") or ""),
            url=str(payload.get("url") or ""),
        )
        _filtered, events = filter_selected_sources(case_id, [(source, "interview", "test", True)])
        observed_action = events[0].action_taken if events else "none"
    elif rail_type == "output":
        _text, events = sanitize_output_text(case_id, str(case.get("payload") or ""))
        observed_action = events[0].action_taken if events else "none"

    passed = observed_action == expect_action
    return {
        "case_id": case_id,
        "rail_type": rail_type,
        "expect_action": expect_action,
        "observed_action": observed_action,
        "passed": passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the minimal injection safety suite.")
    parser.add_argument("--dataset", default="security/minimal_injection_cases.json")
    parser.add_argument("--output", default="security/injection_report.json")
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    os.environ.setdefault("ENABLE_GUARDRAILS", "1")
    os.environ.setdefault("GUARDRAILS_MODE", "minimal_blocking")
    get_settings.cache_clear()

    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    results = [_run_case(case) for case in dataset]
    passed_cases = sum(1 for item in results if item["passed"])
    pass_rate = round(passed_cases / len(results), 4) if results else 0.0
    report = {
        "suite_name": "minimal_injection_suite",
        "total_cases": len(results),
        "passed_cases": passed_cases,
        "pass_rate": pass_rate,
        "threshold": args.threshold,
        "results": results,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if pass_rate < args.threshold:
        raise SystemExit(f"injection suite failed: pass_rate={pass_rate} threshold={args.threshold}")


if __name__ == "__main__":
    main()
