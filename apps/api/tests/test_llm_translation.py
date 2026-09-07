from app.services.llm import (
    StepRecord,
    _build_messages,
    _response_to_action,
    _tool_to_anthropic_schema,
)
from app.services.tools import TOOLS_BY_NAME


def test_tool_to_anthropic_schema_shape() -> None:
    schema = _tool_to_anthropic_schema(TOOLS_BY_NAME["sql_query"])
    assert schema["name"] == "sql_query"
    assert schema["input_schema"]["required"] == ["sql"]


def test_build_messages_starts_with_question_only() -> None:
    messages = _build_messages("why did revenue decline?", [])
    assert messages == [{"role": "user", "content": "why did revenue decline?"}]


def test_build_messages_includes_prior_tool_calls_and_results() -> None:
    history = [
        StepRecord(
            tool_name="sql_query",
            tool_input={"sql": "SELECT 1"},
            tool_output=[{"1": 1}],
        )
    ]
    messages = _build_messages("question", history)
    assert len(messages) == 3
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"][0]["type"] == "tool_use"
    assert messages[1]["content"][0]["name"] == "sql_query"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"][0]["type"] == "tool_result"
    assert messages[2]["content"][0]["is_error"] is False


def test_build_messages_marks_tool_errors() -> None:
    history = [
        StepRecord(
            tool_name="sql_query",
            tool_input={"sql": "DROP TABLE x"},
            tool_output=None,
            tool_error="only SELECT statements are allowed",
        )
    ]
    messages = _build_messages("question", history)
    result_block = messages[2]["content"][0]
    assert result_block["is_error"] is True
    assert "only SELECT" in result_block["content"]


def test_response_to_action_tool_call() -> None:
    content = [
        {"type": "text", "text": "Let me check the data."},
        {"type": "tool_use", "id": "abc", "name": "sql_query", "input": {"sql": "SELECT 1"}},
    ]
    action = _response_to_action(content, "tool_use")
    assert action.kind == "tool_call"
    assert action.tool_name == "sql_query"
    assert action.tool_input == {"sql": "SELECT 1"}
    assert action.thought == "Let me check the data."


def test_response_to_action_final_answer() -> None:
    content = [{"type": "text", "text": "Revenue declined due to churn."}]
    action = _response_to_action(content, "end_turn")
    assert action.kind == "final_answer"
    assert action.final_answer == "Revenue declined due to churn."
