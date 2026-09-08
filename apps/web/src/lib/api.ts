import type {
  ActionItem,
  ActionStatus,
  AgentRun,
  AuditLogEntry,
  DataCatalog,
  Decision,
  DocumentItem,
  GraphResponse,
  RetrievalResult,
  TokenResponse,
  User,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STORAGE_KEY = "forge.session";

interface StoredSession {
  accessToken: string;
  refreshToken: string;
  orgSlug: string;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

type Listener = () => void;

class ApiClient {
  private session: StoredSession | null = null;
  private listeners = new Set<Listener>();
  private refreshPromise: Promise<void> | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        try {
          this.session = JSON.parse(raw);
        } catch {
          this.session = null;
        }
      }
    }
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    this.listeners.forEach((l) => l());
  }

  private persist() {
    if (typeof window === "undefined") return;
    if (this.session) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(this.session));
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    this.notify();
  }

  get isAuthenticated(): boolean {
    return this.session !== null;
  }

  get orgSlug(): string | null {
    return this.session?.orgSlug ?? null;
  }

  private setSession(tokens: TokenResponse, orgSlug: string) {
    this.session = {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      orgSlug,
    };
    this.persist();
  }

  logout() {
    const refreshToken = this.session?.refreshToken;
    this.session = null;
    this.persist();
    if (refreshToken) {
      // Best-effort revoke; don't block the UI on it.
      fetch(`${API_URL}/auth/logout`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {});
    }
  }

  async login(organizationSlug: string, email: string, password: string): Promise<void> {
    const tokens = await this.raw<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ organization_slug: organizationSlug, email, password }),
    });
    this.setSession(tokens, organizationSlug);
  }

  async registerOrganization(name: string, slug: string): Promise<void> {
    await this.raw("/auth/register-organization", {
      method: "POST",
      body: JSON.stringify({ name, slug }),
    });
  }

  async registerUser(
    organizationSlug: string,
    email: string,
    password: string,
    role: string,
  ): Promise<void> {
    await this.raw("/auth/register", {
      method: "POST",
      body: JSON.stringify({ organization_slug: organizationSlug, email, password, role }),
    });
  }

  private async refresh(): Promise<void> {
    if (!this.session) throw new ApiError(401, "not authenticated");
    if (!this.refreshPromise) {
      this.refreshPromise = this.raw<TokenResponse>("/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refresh_token: this.session.refreshToken }),
      })
        .then((tokens) => {
          this.setSession(tokens, this.session!.orgSlug);
        })
        .catch((err) => {
          this.session = null;
          this.persist();
          throw err;
        })
        .finally(() => {
          this.refreshPromise = null;
        });
    }
    return this.refreshPromise;
  }

  private async raw<T>(path: string, init: RequestInit = {}): Promise<T> {
    const resp = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
    if (!resp.ok) {
      let detail: unknown = resp.statusText;
      try {
        const body = await resp.json();
        detail = body.detail ?? body;
      } catch {
        // no JSON body
      }
      throw new ApiError(resp.status, detail);
    }
    if (resp.status === 204) return undefined as T;
    return (await resp.json()) as T;
  }

  async request<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
    const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
    if (this.session) headers.Authorization = `Bearer ${this.session.accessToken}`;
    try {
      return await this.raw<T>(path, { ...init, headers });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && this.session && !retried) {
        await this.refresh();
        return this.request<T>(path, init, true);
      }
      throw err;
    }
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
  }

  // ---- Typed endpoints ----

  me() {
    return this.get<User>("/auth/me");
  }

  listRuns() {
    return this.get<AgentRun[]>("/agents/runs");
  }

  getRun(id: string) {
    return this.get<AgentRun>(`/agents/runs/${id}`);
  }

  createRun(question: string) {
    return this.post<AgentRun>("/agents/runs", { question });
  }

  synthesizeDecision(runId: string) {
    return this.post<Decision>(`/agents/runs/${runId}/decision`);
  }

  getDecisionForRun(runId: string) {
    return this.get<Decision>(`/agents/runs/${runId}/decision`);
  }

  listDecisions() {
    return this.get<Decision[]>("/decisions");
  }

  listActions() {
    return this.get<ActionItem[]>("/actions");
  }

  proposeAction(input: {
    action_type: string;
    description: string;
    parameters: Record<string, unknown>;
    decision_id?: string;
  }) {
    return this.post<ActionItem>("/actions", input);
  }

  transitionAction(id: string, transition: "approve" | "reject" | "execute") {
    return this.post<ActionItem>(`/actions/${id}/${transition}`);
  }

  runSqlQuery(sql: string) {
    return this.post<{ rows: Record<string, unknown>[]; row_count: number }>("/data/query", {
      sql,
    });
  }

  getCatalog() {
    return this.get<DataCatalog>("/data/catalog");
  }

  searchDocuments(query: string, top_k = 8) {
    return this.post<{ results: RetrievalResult[] }>("/retrieval/search", { query, top_k });
  }

  listDocuments() {
    return this.get<DocumentItem[]>("/documents");
  }

  ingestDocument(title: string, content: string, source = "upload") {
    return this.post<DocumentItem>("/documents", { title, content, source });
  }

  getGraph(entityType: string, entityId: string, depth = 1) {
    return this.get<GraphResponse>(
      `/knowledge-graph/${entityType}/${entityId}?depth=${depth}`,
    );
  }

  listAudit() {
    return this.get<AuditLogEntry[]>("/audit/logs");
  }

  readyz() {
    return this.raw<{ status: string; checks: Record<string, string> }>("/readyz");
  }
}

export const api = new ApiClient();
export type { ActionStatus };
