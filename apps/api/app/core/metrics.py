from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

http_requests_total = Counter(
    "forge_http_requests_total",
    "HTTP requests by method, path template, and status code",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "forge_http_request_duration_seconds",
    "HTTP request duration in seconds by method and path template",
    ["method", "path"],
)

agent_runs_total = Counter(
    "forge_agent_runs_total",
    "Agent runs by final status (completed, max_steps_exceeded)",
    ["status"],
)

agent_tool_calls_total = Counter(
    "forge_agent_tool_calls_total",
    "Agent tool invocations by tool name and outcome (ok, error)",
    ["tool_name", "outcome"],
)

decisions_synthesized_total = Counter(
    "forge_decisions_synthesized_total",
    "Decisions synthesized by outcome (ok, error)",
    ["outcome"],
)

actions_total = Counter(
    "forge_actions_total",
    "Action lifecycle transitions by action type and resulting status",
    ["action_type", "status"],
)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
