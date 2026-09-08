"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { DataCatalog, GraphResponse, RetrievalResult } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  Input,
  Label,
  PageHeader,
  Spinner,
  Textarea,
} from "@/components/ui";

const TABS = ["SQL query", "Document search", "Knowledge graph"] as const;
type Tab = (typeof TABS)[number];

export default function DataExplorerPage() {
  const [tab, setTab] = useState<Tab>("SQL query");
  const [catalog, setCatalog] = useState<DataCatalog | null>(null);

  useEffect(() => {
    api
      .getCatalog()
      .then(setCatalog)
      .catch(() => setCatalog(null));
  }, []);

  return (
    <>
      <PageHeader
        title="Data explorer"
        description="Query, search, and traverse your organization's data the same way the agent does."
      />

      <div className="mb-6 flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === t
                ? "border-accent text-accent"
                : "border-transparent text-fg-muted hover:text-fg"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "SQL query" && <SqlTab catalog={catalog} />}
      {tab === "Document search" && <SearchTab />}
      {tab === "Knowledge graph" && <GraphTab catalog={catalog} />}
    </>
  );
}

function SqlTab({ catalog }: { catalog: DataCatalog | null }) {
  const [sql, setSql] = useState("SELECT name, status FROM customers LIMIT 20");
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setError(null);
    setLoading(true);
    try {
      const resp = await api.runSqlQuery(sql);
      setRows(resp.rows);
    } catch (err) {
      setError(err instanceof ApiError && typeof err.detail === "string" ? err.detail : "Query failed.");
      setRows(null);
    } finally {
      setLoading(false);
    }
  }

  const columns = rows && rows.length > 0 ? Object.keys(rows[0]) : [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
      <div className="lg:col-span-3">
        <Textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          rows={4}
          className="font-mono"
        />
        <div className="mt-3 flex items-center justify-between">
          <p className="text-xs text-fg-subtle">Read-only SELECT, automatically scoped to your organization.</p>
          <Button onClick={run} loading={loading}>
            Run query
          </Button>
        </div>

        {error && (
          <div className="mt-4">
            <ErrorBanner message={error} />
          </div>
        )}

        {rows && (
          <Card className="mt-4 overflow-x-auto">
            {rows.length === 0 ? (
              <EmptyState title="No rows returned" />
            ) : (
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {columns.map((c) => (
                      <th key={c} className="whitespace-nowrap px-4 py-2 font-mono text-xs font-medium text-fg-muted">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className="border-b border-border last:border-0">
                      {columns.map((c) => (
                        <td key={c} className="whitespace-nowrap px-4 py-2 font-mono text-xs text-fg">
                          {String(row[c] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        )}
      </div>

      <Card className="h-fit p-4">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-muted">Schema</h3>
        {catalog ? (
          <div className="space-y-3">
            {catalog.tables.map((table) => (
              <div key={table}>
                <button
                  onClick={() => setSql(`SELECT * FROM ${table} LIMIT 20`)}
                  className="font-mono text-xs font-medium text-accent hover:text-accent-hover"
                >
                  {table}
                </button>
                <p className="mt-0.5 font-mono text-[11px] leading-relaxed text-fg-subtle">
                  {catalog.schema[table]?.join(", ")}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <Spinner />
        )}
      </Card>
    </div>
  );
}

function SearchTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RetrievalResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    if (!query.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const resp = await api.searchDocuments(query.trim());
      setResults(resp.results);
    } catch {
      setError("Search failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="e.g. customer evaluating a competitor"
        />
        <Button onClick={search} loading={loading}>
          Search
        </Button>
      </div>
      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      )}
      {results && (
        <div className="mt-4 space-y-3">
          {results.length === 0 ? (
            <EmptyState title="No matching documents" />
          ) : (
            results.map((r, i) => (
              <Card key={i} className="p-4">
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-sm font-medium text-fg">{r.document_title}</span>
                  <Badge tone="neutral">score {r.score.toFixed(2)}</Badge>
                </div>
                <p className="line-clamp-3 text-sm text-fg-muted">{r.content}</p>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function GraphTab({ catalog }: { catalog: DataCatalog | null }) {
  const [entityType, setEntityType] = useState("customers");
  const [entityId, setEntityId] = useState("");
  const [depth, setDepth] = useState(1);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function lookup() {
    if (!entityId.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const g = await api.getGraph(entityType, entityId.trim(), depth);
      setGraph(g);
    } catch (err) {
      setError(err instanceof ApiError ? "Entity not found in this tenant." : "Lookup failed.");
      setGraph(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <Label>Entity type</Label>
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="rounded-lg border border-border-strong bg-bg-inset px-3 py-2 text-sm text-fg outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          >
            {(catalog?.tables ?? ["customers"]).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1 min-w-48">
          <Label>Entity ID</Label>
          <Input value={entityId} onChange={(e) => setEntityId(e.target.value)} placeholder="UUID" />
        </div>
        <div className="w-24">
          <Label>Depth</Label>
          <Input
            type="number"
            min={1}
            max={3}
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
          />
        </div>
        <Button onClick={lookup} loading={loading}>
          Explore
        </Button>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      )}

      {graph && (
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Card className="p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-muted">
              Nodes ({graph.nodes.length})
            </h3>
            <ul className="space-y-1.5">
              {graph.nodes.map((n) => (
                <li key={`${n.type}:${n.id}`} className="flex items-center gap-2 text-sm">
                  <Badge tone="neutral">{n.type}</Badge>
                  <span className="truncate text-fg">{n.label}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-muted">
              Edges ({graph.edges.length})
            </h3>
            <ul className="space-y-1.5 font-mono text-xs text-fg-muted">
              {graph.edges.map((e, i) => (
                <li key={i} className="truncate">
                  {e.source} <span className="text-accent">→</span> {e.target}{" "}
                  <span className="text-fg-subtle">({e.relation})</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
