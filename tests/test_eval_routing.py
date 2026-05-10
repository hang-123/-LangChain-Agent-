from __future__ import annotations

from api.evals.harness import _score_routing


def test_score_routing_correct_intent_and_workflow():
    """Correct intent + workflow = high score."""
    case = {
        "routing_ground_truth": {
            "expected_intent": "match",
            "expected_workflow": "wf_match_v2",
            "expected_missing_artifacts": [],
            "required_steps": ["SearchOrchestrator", "JobAnalyzer", "MatchingEngine"],
        }
    }
    state = {
        "intent": "match",
        "workflow_id": "wf_match_v2",
        "missing_artifacts": [],
        "run_trace": [
            {"node": "Supervisor", "phase": "started"},
            {"node": "SearchOrchestrator", "phase": "completed"},
            {"node": "JobAnalyzer", "phase": "completed"},
            {"node": "MatchingEngine", "phase": "completed"},
        ],
    }
    score = _score_routing(case, state)
    assert score == 100, f"Expected 100, got {score}"


def test_score_routing_wrong_workflow():
    """Wrong workflow = significant penalty."""
    case = {
        "routing_ground_truth": {
            "expected_intent": "match",
            "expected_workflow": "wf_match_v2",
            "expected_missing_artifacts": [],
            "required_steps": ["SearchOrchestrator"],
        }
    }
    state = {
        "intent": "match",
        "workflow_id": "wf_resume_tailor_v2",
        "missing_artifacts": [],
        "run_trace": [],
    }
    score = _score_routing(case, state)
    assert score < 75, f"Expected penalty for wrong workflow, got {score}"


def test_score_routing_missing_steps():
    """Missing required steps = penalty."""
    case = {
        "routing_ground_truth": {
            "expected_intent": "match",
            "expected_workflow": "wf_match_v2",
            "expected_missing_artifacts": [],
            "required_steps": ["SearchOrchestrator", "JobAnalyzer", "MatchingEngine"],
        }
    }
    state = {
        "intent": "match",
        "workflow_id": "wf_match_v2",
        "missing_artifacts": [],
        "run_trace": [
            {"node": "SearchOrchestrator", "phase": "completed"},
        ],
    }
    score = _score_routing(case, state)
    assert score < 100, f"Expected penalty for missing steps, got {score}"


def test_score_routing_undetected_missing_inputs():
    """Undetected missing inputs = penalty."""
    case = {
        "routing_ground_truth": {
            "expected_intent": "resume_tailor",
            "expected_workflow": "wf_resume_tailor_v2",
            "expected_missing_artifacts": ["candidate_profile"],
            "required_steps": [],
        }
    }
    state = {
        "intent": "resume_tailor",
        "workflow_id": "wf_resume_tailor_v2",
        "missing_artifacts": [],
    }
    score = _score_routing(case, state)
    assert score < 100, f"Expected penalty for undetected missing input, got {score}"
