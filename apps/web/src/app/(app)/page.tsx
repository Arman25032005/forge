"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { ActionItem, AgentRun, Decision } from "@/lib/types";
import { Badge, Card, EmptyState, PageHeader, Spinner, statusTone } from "@/components/ui";
import { can } from "@/lib/types";

export default function DashboardPage() {
  const { user } = useAuth();
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [actions, setActions] = useState<ActionItem[] | null>(null);
  const [decisions, setDecisions] = useState<Decision[] | null>(null);
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    api.listRuns().then(setRuns).catch(() => setRuns([]));
    api.listActions().then(setActions).catch(() => setActions([]));
    api.listDecisions().then(setDecisions).catch(() => setDecisions([]));
    api
      .readyz()
      .then((r) => setApiHealthy(r.status === "ok" || r.status === "degraded"))
      .catch(() => setApiHealthy(false));
  }, []);

  const loading = runs === null || actions === null || decisions === null;
  const pendingActions = actions?.filter((a) => a.status === "proposed") ?? [];
  const completedRuns = runs?.filter((r) => r.status === "completed") ?? [];

  return (
    <>
      <PageHeader
        title={`Welcome back${user ? `, ${user.email.split("@")[0]}` : ""}`}
        description="A live view of your organization's investigations, decisions, and pending approvals."
      />

      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Kpi label="Investigations" value={runs?.length} href="/investigations" />
        <Kpi label="Completed" value={completedRuns.length} href="/investigations" />
        <Kpi label="Decisions" value={decisions?.length} href="/decisions" />
        <Kpi
          label="Pending actions"
          value={pendingActions.length}
          href="/actions"
          accent={pendingActions.length > 0}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-fg">Recent investigations</h2>
            <Link href="/investigations" className="text-xs font-medium text-accent hover:text-accent-hover">
              View all
            </Link>
          </div>
          {loading ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : runs && runs.length > 0 ? (
            <ul className="space-y-1">
              {runs.slice(0, 5).map((run) => (
                <li key={run.id}>
                  <Link
                    href={`/investigations/${run.id}`}
                    className="flex items-center justify-between gap-3 rounded-lg px-2 py-2.5 hover:bg-bg-inset"
                  >
                    <span className="truncate text-sm text-fg">{run.question}</span>
                    <Badge tone={statusTone(run.status)}>{run.status.replace(/_/g, " ")}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No investigations yet"
              description="Ask the agent a business question to get started."
            />
          )}
        </Card>

        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-fg">Awaiting approval</h2>
            <Link href="/actions" className="text-xs font-medium text-accent hover:text-accent-hover">
              View all
            </Link>
          </div>
          {loading ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : pendingActions.length > 0 ? (
            <ul className="space-y-1">
              {pendingActions.slice(0, 5).map((action) => (
                <li
                  key={action.id}
                  className="flex items-center justify-between gap-3 rounded-lg px-2 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm text-fg">{action.description}</p>
                    <p className="text-xs text-fg-subtle">{action.action_type}</p>
                  </div>
                  <Badge tone="accent">proposed</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="Nothing pending"
              description={
                can(user?.role, "action.propose")
                  ? "Propose an action from a decision to see it here."
                  : "Approved and executed actions will show up in the actions log."
              }
            />
          )}
        </Card>
      </div>

      {apiHealthy === false && (
        <p className="mt-6 text-center text-xs text-fg-subtle">
          Having trouble connecting to the API — check that the backend is running.
        </p>
      )}
    </>
  );
}

function Kpi({
  label,
  value,
  href,
  accent = false,
}: {
  label: string;
  value: number | undefined;
  href: string;
  accent?: boolean;
}) {
  return (
    <Link href={href}>
      <Card className="p-4 transition-colors hover:border-border-strong">
        <p className="text-xs font-medium text-fg-muted">{label}</p>
        <p className={`mt-1.5 text-2xl font-semibold tabular-nums ${accent ? "text-accent" : "text-fg"}`}>
          {value ?? "—"}
        </p>
      </Card>
    </Link>
  );
}
