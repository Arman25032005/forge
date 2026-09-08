from app.services.llm import (
    MAX_TOOL_RESULT_CHARS_IN_PROMPT,
    StepRecord,
    _build_messages,
    _build_openai_messages,
    _openai_message_to_action,
    _response_to_action,
    _tool_to_anthropic_schema,
    _tool_to_openai_schema,
    _truncate_for_prompt,
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


def test_tool_to_openai_schema_shape() -> None:
    schema = _tool_to_openai_schema(TOOLS_BY_NAME["sql_query"])
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "sql_query"
    assert schema["function"]["parameters"]["required"] == ["sql"]


def test_build_openai_messages_starts_with_system_and_question() -> None:
    messages = _build_openai_messages("why did revenue decline?", [])
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "why did revenue decline?"}


def test_build_openai_messages_includes_prior_tool_calls_and_results() -> None:
    history = [
        StepRecord(tool_name="sql_query", tool_input={"sql": "SELECT 1"}, tool_output=[{"1": 1}])
    ]
    messages = _build_openai_messages("question", history)
    assert len(messages) == 4  # system, user, assistant tool_call, tool result
    assistant_msg = messages[2]
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["tool_calls"][0]["function"]["name"] == "sql_query"
    tool_msg = messages[3]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == assistant_msg["tool_calls"][0]["id"]


def test_openai_message_to_action_tool_call() -> None:
    message = {
        "content": "Let me check the data.",
        "tool_calls": [
            {
                "id": "abc",
                "function": {"name": "sql_query", "arguments": '{"sql": "SELECT 1"}'},
            }
        ],
    }
    action = _openai_message_to_action(message)
    assert action.kind == "tool_call"
    assert action.tool_name == "sql_query"
    assert action.tool_input == {"sql": "SELECT 1"}
    assert action.thought == "Let me check the data."


def test_openai_message_to_action_final_answer() -> None:
    action = _openai_message_to_action(
        {"content": "Revenue declined due to churn.", "tool_calls": []}
    )
    assert action.kind == "final_answer"
    assert action.final_answer == "Revenue declined due to churn."


def test_openai_message_to_action_handles_malformed_arguments() -> None:
    message = {
        "content": None,
        "tool_calls": [{"id": "x", "function": {"name": "sql_query", "arguments": "not json"}}],
    }
    action = _openai_message_to_action(message)
    assert action.kind == "tool_call"
    assert action.tool_input == {}


def test_truncate_for_prompt_leaves_short_content_alone() -> None:
    short = "x" * 100
    assert _truncate_for_prompt(short) == short


def test_truncate_for_prompt_caps_long_content() -> None:
    # Regression test for a real bug found live: resending a large tool
    # result (e.g. a multi-row SQL join) every step pushed a 4-step
    # conversation over Groq's free-tier token-per-minute budget, failing
    # the whole run with a 413 instead of degrading gracefully.
    long = "x" * (MAX_TOOL_RESULT_CHARS_IN_PROMPT * 3)
    truncated = _truncate_for_prompt(long)
    assert len(truncated) < len(long)
    assert truncated.startswith("x" * MAX_TOOL_RESULT_CHARS_IN_PROMPT)
    assert "truncated" in truncated
