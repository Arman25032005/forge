"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types";
import { Badge, Card, EmptyState, PageHeader, Spinner, statusTone } from "@/components/ui";

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLogEntry[] | null>(null);

  useEffect(() => {
    api
      .listAudit()
      .then(setLogs)
      .catch(() => setLogs([]));
  }, []);

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Security-relevant events for your organization — logins, document access, data queries."
      />

      {logs === null ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : logs.length === 0 ? (
        <EmptyState title="No audit events yet" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-2 text-xs font-medium text-fg-muted">Action</th>
                <th className="px-4 py-2 text-xs font-medium text-fg-muted">Resource</th>
                <th className="px-4 py-2 text-xs font-medium text-fg-muted">Outcome</th>
                <th className="px-4 py-2 text-xs font-medium text-fg-muted">When</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-border last:border-0">
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-fg">{log.action}</td>
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-fg-muted">{log.resource}</td>
                  <td className="px-4 py-2">
                    <Badge tone={statusTone(log.outcome)}>{log.outcome}</Badge>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-xs text-fg-subtle">
                    {log.created_at ? new Date(log.created_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
