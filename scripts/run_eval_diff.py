from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.core.contracts import EvalSuiteSummary
from api.evals.diffing import build_eval_diff, render_eval_diff_markdown


def _load_summary(path: str | Path) -> EvalSuiteSummary:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return EvalSuiteSummary.model_validate(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two eval suite summaries and emit diff artifacts.")
    parser.add_argument("--baseline", required=True, help="Path to the baseline eval summary JSON.")
    parser.add_argument("--current", required=True, help="Path to the current eval summary JSON.")
    parser.add_argument("--output-json", default="logs/ci/eval_diff.json", help="Output path for eval diff JSON.")
    parser.add_argument("--output-md", default="logs/ci/eval_diff.md", help="Output path for eval diff markdown.")
    args = parser.parse_args()

    diff = build_eval_diff(_load_summary(args.baseline), _load_summary(args.current))
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_eval_diff_markdown(diff), encoding="utf-8")
    print(json.dumps(diff, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
