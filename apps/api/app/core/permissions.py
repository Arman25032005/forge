from app.models.user import Role


class Permission:
    DOCUMENT_READ = "document.read"
    DOCUMENT_WRITE = "document.write"
    DATA_QUERY = "data.query"
    AGENT_EXECUTE = "agent.execute"
    TOOL_EXECUTE = "tool.execute"
    ACTION_PROPOSE = "action.propose"
    ACTION_EXECUTE = "action.execute"
    AUDIT_READ = "audit.read"
    USER_MANAGE = "user.manage"
    POLICY_MANAGE = "policy.manage"


ALL_PERMISSIONS = frozenset(
    v for k, v in vars(Permission).items() if not k.startswith("_") and isinstance(v, str)
)

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.ADMIN: ALL_PERMISSIONS,
    Role.ANALYST: frozenset(
        {
            Permission.DOCUMENT_READ,
            Permission.DATA_QUERY,
            Permission.AGENT_EXECUTE,
            Permission.TOOL_EXECUTE,
            Permission.ACTION_PROPOSE,
            Permission.AUDIT_READ,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Permission.DOCUMENT_READ,
            Permission.DATA_QUERY,
            Permission.ACTION_PROPOSE,
            Permission.ACTION_EXECUTE,
            Permission.AUDIT_READ,
        }
    ),
    Role.VIEWER: frozenset({Permission.DOCUMENT_READ, Permission.AUDIT_READ}),
}


def role_has_permission(role: Role, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
