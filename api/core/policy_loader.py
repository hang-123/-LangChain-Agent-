from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.core.policies import HarnessPolicy


DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "defaults.json"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
            continue
        merged[key] = value
    return merged


def _read_policy_payload(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("YAML policy loading requires PyYAML to be installed.") from exc
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"policy payload at {path} must be a mapping")
        return payload
    raise ValueError(f"unsupported policy file type: {path.suffix}")


@lru_cache(maxsize=8)
def load_policy(policy_path: str | Path | None = None) -> HarnessPolicy:
    base_payload = _read_policy_payload(DEFAULT_POLICY_PATH)
    if policy_path is not None:
        override_payload = _read_policy_payload(Path(policy_path))
        base_payload = _deep_merge(base_payload, override_payload)
    return HarnessPolicy.model_validate(base_payload)


def load_policy_with_overrides(
    *,
    policy_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> HarnessPolicy:
    policy = load_policy(policy_path)
    if not overrides:
        return policy
    merged = _deep_merge(policy.model_dump(mode="json"), overrides)
    return HarnessPolicy.model_validate(merged)


def coerce_policy(raw_policy: Any | None) -> HarnessPolicy:
    if isinstance(raw_policy, HarnessPolicy):
        return raw_policy
    if isinstance(raw_policy, dict) and raw_policy:
        return HarnessPolicy.model_validate(raw_policy)
    return load_policy()


def policy_from_state(state: dict[str, Any]) -> HarnessPolicy:
    return coerce_policy(state.get("policy"))
