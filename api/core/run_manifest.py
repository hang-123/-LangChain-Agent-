from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from api.core.harness import utc_now_iso
from api.core.policies import HarnessPolicy
from api.core.prompt_loader import PROMPT_DIR
from api.core.settings import get_settings


class ExperimentFlags(BaseModel):
    policy_control_plane: bool = True
    structured_contracts: bool = True
    rule_checker_review: bool = True
    renderer_first_report: bool = True
    eval_as_default: bool = True
    persist_run_artifacts: bool = True
    otel_tracing: bool = False
    query_store_dual_write: bool = False
    sqlite_cache: bool = False
    guardrails_minimal: bool = False


class ExperimentAssignment(BaseModel):
    experiment_id: str = ""
    variant: str = "control"
    rollout_percentage: int = Field(default=0, ge=0, le=100)
    assignment_source: str = "disabled"


class RunManifest(BaseModel):
    run_id: str
    query: str
    requested_at: str
    prompt_version: str
    policy_version: str
    code_version: str
    model_name: str
    research_case_id: str = ""
    experiment_id: str = ""
    variant: str = "control"
    rollout_percentage: int = Field(default=0, ge=0, le=100)
    assignment_source: str = "disabled"
    experiment_flags: ExperimentFlags = Field(default_factory=ExperimentFlags)


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def compute_prompt_version() -> str:
    payload_parts: list[str] = []
    for path in sorted(PROMPT_DIR.glob("*.txt")):
        payload_parts.append(f"{path.name}:{path.read_text(encoding='utf-8')}")
    return _short_hash("\n".join(payload_parts) or "no-prompts")


def resolve_code_version() -> str:
    env_version = os.getenv("CODE_VERSION", "").strip()
    if env_version:
        return env_version
    repo_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _stable_bucket(*parts: str) -> int:
    joined = "::".join(parts)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def resolve_experiment_assignment(*, run_id: str, query: str) -> ExperimentAssignment:
    settings = get_settings()
    experiment_id = settings.experiment_id.strip()
    variants = [item.strip() for item in settings.experiment_variants.split(",") if item.strip()]
    rollout = max(0, min(100, int(settings.experiment_rollout_pct or 0)))
    forced = settings.force_variant.strip()

    if forced:
        return ExperimentAssignment(
            experiment_id=experiment_id or "manual_override",
            variant=forced,
            rollout_percentage=100,
            assignment_source="forced",
        )

    if not experiment_id or rollout <= 0 or len(variants) <= 1:
        return ExperimentAssignment(
            experiment_id=experiment_id,
            variant="control",
            rollout_percentage=rollout,
            assignment_source="disabled" if not experiment_id or rollout <= 0 else "single_variant",
        )

    rollout_bucket = _stable_bucket(experiment_id, run_id, query, "rollout")
    if rollout_bucket >= rollout:
        return ExperimentAssignment(
            experiment_id=experiment_id,
            variant="control",
            rollout_percentage=rollout,
            assignment_source="stable_hash_control",
        )

    variant_bucket = _stable_bucket(experiment_id, run_id, query, "variant")
    variant_index = variant_bucket % len(variants)
    return ExperimentAssignment(
        experiment_id=experiment_id,
        variant=variants[variant_index],
        rollout_percentage=rollout,
        assignment_source="stable_hash_variant",
    )


def build_run_manifest(
    *,
    run_id: str,
    query: str,
    policy: HarnessPolicy,
    research_case_id: str = "",
    experiment_flags: ExperimentFlags | None = None,
) -> RunManifest:
    settings = get_settings()
    assignment = resolve_experiment_assignment(run_id=run_id, query=query)
    return RunManifest(
        run_id=run_id,
        query=query,
        requested_at=utc_now_iso(),
        prompt_version=compute_prompt_version(),
        policy_version=policy.version,
        code_version=resolve_code_version(),
        model_name=settings.openai_model,
        research_case_id=research_case_id,
        experiment_id=assignment.experiment_id,
        variant=assignment.variant,
        rollout_percentage=assignment.rollout_percentage,
        assignment_source=assignment.assignment_source,
        experiment_flags=experiment_flags
        or ExperimentFlags(
            otel_tracing=bool(settings.enable_otel),
            query_store_dual_write=bool(settings.enable_query_store),
            sqlite_cache=bool(settings.enable_cache),
            guardrails_minimal=bool(settings.enable_guardrails),
        ),
    )
