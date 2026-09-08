export type Role = "ADMIN" | "ANALYST" | "OPERATOR" | "VIEWER";

export interface User {
  id: string;
  organization_id: string;
  email: string;
  role: Role;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AgentStep {
  step_index: number;
  thought: string | null;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: unknown;
}

export type AgentRunStatus = "running" | "completed" | "max_steps_exceeded" | "failed";

export interface AgentRun {
  id: string;
  question: string;
  status: AgentRunStatus;
  final_answer: string | null;
  error: string | null;
  created_at: string;
  steps: AgentStep[];
}

export interface Decision {
  id: string;
  run_id: string;
  conclusion: string;
  confidence: number;
  evidence: { step_index: number; summary: string }[];
  recommended_actions: string[];
  status: string;
  created_at: string;
}

export type ActionStatus = "proposed" | "approved" | "rejected" | "executed" | "failed";

export interface ActionItem {
  id: string;
  decision_id: string | null;
  action_type: string;
  description: string;
  parameters: Record<string, unknown>;
  status: ActionStatus;
  proposed_by: string;
  approved_by: string | null;
  executed_at: string | null;
  result: Record<string, unknown> | null;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  title: string;
  source: string;
  customer_id: string | null;
  created_at: string;
}

export interface RetrievalResult {
  document_id: string;
  document_title: string;
  chunk_index: number;
  content: string;
  score: number;
}

export interface GraphNode {
  type: string;
  id: string;
  label: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface DataCatalog {
  tables: string[];
  schema: Record<string, string[]>;
}

export interface AuditLogEntry {
  id: string;
  action: string;
  resource: string;
  outcome: string;
  created_at: string | null;
}

export const ROLE_PERMISSIONS: Record<Role, string[]> = {
  ADMIN: [
    "document.read",
    "document.write",
    "data.query",
    "agent.execute",
    "tool.execute",
    "action.propose",
    "action.execute",
    "audit.read",
    "user.manage",
    "policy.manage",
  ],
  ANALYST: [
    "document.read",
    "data.query",
    "agent.execute",
    "tool.execute",
    "action.propose",
    "audit.read",
  ],
  OPERATOR: ["document.read", "data.query", "action.propose", "action.execute", "audit.read"],
  VIEWER: ["document.read", "audit.read"],
};

export function can(role: Role | undefined, permission: string): boolean {
  if (!role) return false;
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false;
}
