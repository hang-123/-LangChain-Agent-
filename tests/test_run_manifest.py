from __future__ import annotations

from api.core.policy_loader import load_policy
from api.core.run_manifest import build_run_manifest, resolve_experiment_assignment
from api.core.settings import get_settings


def test_forced_variant_is_written_to_run_manifest(monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ID", "report-polish-ab")
    monkeypatch.setenv("FORCE_VARIANT", "treatment")
    monkeypatch.setenv("ENABLE_OTEL", "1")
    monkeypatch.setenv("ENABLE_CACHE", "1")
    monkeypatch.setenv("ENABLE_QUERY_STORE", "1")
    monkeypatch.setenv("ENABLE_GUARDRAILS", "1")
    get_settings.cache_clear()

    policy = load_policy()
    manifest = build_run_manifest(run_id="run-123", query="字节后端", policy=policy)

    assert manifest.experiment_id == "report-polish-ab"
    assert manifest.variant == "treatment"
    assert manifest.assignment_source == "forced"
    assert manifest.experiment_flags.otel_tracing is True
    assert manifest.experiment_flags.sqlite_cache is True
    assert manifest.experiment_flags.query_store_dual_write is True
    assert manifest.experiment_flags.guardrails_minimal is True

    get_settings.cache_clear()


def test_stable_hash_assignment_returns_control_or_variant(monkeypatch):
    monkeypatch.delenv("FORCE_VARIANT", raising=False)
    monkeypatch.setenv("EXPERIMENT_ID", "review-ab")
    monkeypatch.setenv("EXPERIMENT_ROLLOUT_PCT", "100")
    monkeypatch.setenv("EXPERIMENT_VARIANTS", "control,treatment")
    get_settings.cache_clear()

    assignment = resolve_experiment_assignment(run_id="run-abc", query="美团后端实习")

    assert assignment.experiment_id == "review-ab"
    assert assignment.variant in {"control", "treatment"}
    assert assignment.assignment_source == "stable_hash_variant"

    get_settings.cache_clear()
