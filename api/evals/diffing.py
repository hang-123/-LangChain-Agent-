from __future__ import annotations

from typing import Any

from api.core.contracts import CaseEvaluation, EvalSuiteSummary


def _case_index(items: list[CaseEvaluation]) -> dict[str, CaseEvaluation]:
    return {item.case_id: item for item in items}


def build_eval_diff(baseline: EvalSuiteSummary, current: EvalSuiteSummary) -> dict[str, Any]:
    baseline_cases = _case_index(baseline.case_results)
    current_cases = _case_index(current.case_results)

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    unchanged: list[str] = []

    for case_id in sorted(set(baseline_cases) | set(current_cases)):
        before = baseline_cases.get(case_id)
        after = current_cases.get(case_id)
        if before is None or after is None:
            continue

        score_delta = after.score - before.score
        passed_delta = int(after.passed) - int(before.passed)
        entry = {
            "case_id": case_id,
            "baseline_score": before.score,
            "current_score": after.score,
            "score_delta": score_delta,
            "baseline_passed": before.passed,
            "current_passed": after.passed,
            "baseline_root_cause": before.root_cause,
            "current_root_cause": after.root_cause,
            "current_failures": after.failures[:5],
        }
        if score_delta < 0 or (before.passed and not after.passed):
            regressions.append(entry)
        elif score_delta > 0 or (not before.passed and after.passed):
            improvements.append(entry)
        else:
            unchanged.append(case_id)

    root_cause_delta: dict[str, int] = {}
    all_root_causes = set(baseline.root_cause_breakdown) | set(current.root_cause_breakdown)
    for key in all_root_causes:
        root_cause_delta[key] = current.root_cause_breakdown.get(key, 0) - baseline.root_cause_breakdown.get(key, 0)

    regressions.sort(key=lambda item: (item["score_delta"], item["case_id"]))
    improvements.sort(key=lambda item: (-item["score_delta"], item["case_id"]))

    return {
        "baseline_suite": baseline.suite_name,
        "current_suite": current.suite_name,
        "baseline_average_score": baseline.average_score,
        "current_average_score": current.average_score,
        "average_score_delta": round(current.average_score - baseline.average_score, 2),
        "baseline_passed_cases": baseline.passed_cases,
        "current_passed_cases": current.passed_cases,
        "passed_cases_delta": current.passed_cases - baseline.passed_cases,
        "root_cause_delta": root_cause_delta,
        "regressions": regressions[:10],
        "improvements": improvements[:10],
        "unchanged_cases": unchanged,
        "missing_from_baseline": sorted(set(current_cases) - set(baseline_cases)),
        "missing_from_current": sorted(set(baseline_cases) - set(current_cases)),
    }


def render_eval_diff_markdown(diff: dict[str, Any]) -> str:
    lines = [
        "# Eval Diff Report",
        "",
        f"- Baseline suite: `{diff['baseline_suite']}`",
        f"- Current suite: `{diff['current_suite']}`",
        f"- Average score delta: `{diff['average_score_delta']}`",
        f"- Passed cases delta: `{diff['passed_cases_delta']}`",
        "",
        "## Top Regressions",
        "",
    ]
    regressions = diff.get("regressions") or []
    if not regressions:
        lines.append("- None")
    else:
        for item in regressions:
            failure_text = "; ".join(item.get("current_failures") or []) or "No failure details"
            lines.append(
                f"- `{item['case_id']}`: score `{item['baseline_score']} -> {item['current_score']}`; "
                f"passed `{item['baseline_passed']} -> {item['current_passed']}`; {failure_text}"
            )

    lines.extend(["", "## Top Improvements", ""])
    improvements = diff.get("improvements") or []
    if not improvements:
        lines.append("- None")
    else:
        for item in improvements:
            lines.append(
                f"- `{item['case_id']}`: score `{item['baseline_score']} -> {item['current_score']}`; "
                f"passed `{item['baseline_passed']} -> {item['current_passed']}`"
            )

    lines.extend(["", "## Root Cause Delta", ""])
    for key, value in sorted((diff.get("root_cause_delta") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")

    return "\n".join(lines) + "\n"

