import json

import pytest

from app.services.decision_synthesis import (
    DecisionSynthesisError,
    StepSummary,
    _build_synthesis_messages,
    _parse_decision_json,
)


def test_build_synthesis_messages_includes_question_and_steps() -> None:
    steps = [
        StepSummary(
            step_index=0,
            tool_name="sql_query",
            tool_input={"sql": "SELECT 1"},
            tool_output=[{"1": 1}],
        )
    ]
    messages = _build_synthesis_messages("why did revenue decline?", steps)
    assert len(messages) == 1
    content = messages[0]["content"]
    assert "why did revenue decline?" in content
    assert "sql_query" in content
    assert "Step 0" in content


def test_parse_decision_json_valid() -> None:
    payload = json.dumps(
        {
            "conclusion": "Revenue declined due to churn.",
            "confidence": 0.8,
            "evidence": [{"step_index": 0, "summary": "declining transactions"}],
            "recommended_actions": ["Reach out to at-risk customers"],
        }
    )
    draft = _parse_decision_json(payload, valid_step_indices={0})
    assert draft.confidence == 0.8
    assert draft.conclusion == "Revenue declined due to churn."
    assert draft.recommended_actions == ["Reach out to at-risk customers"]


def test_parse_decision_json_rejects_fabricated_evidence() -> None:
    payload = json.dumps(
        {
            "conclusion": "x",
            "confidence": 0.5,
            "evidence": [{"step_index": 7, "summary": "made up"}],
            "recommended_actions": [],
        }
    )
    with pytest.raises(DecisionSynthesisError, match="step 7"):
        _parse_decision_json(payload, valid_step_indices={0, 1})


def test_parse_decision_json_rejects_out_of_range_confidence() -> None:
    payload = json.dumps(
        {"conclusion": "x", "confidence": 1.5, "evidence": [], "recommended_actions": []}
    )
    with pytest.raises(DecisionSynthesisError, match="confidence"):
        _parse_decision_json(payload, valid_step_indices=set())


def test_parse_decision_json_rejects_invalid_json() -> None:
    with pytest.raises(DecisionSynthesisError, match="valid JSON"):
        _parse_decision_json("not json", valid_step_indices=set())
