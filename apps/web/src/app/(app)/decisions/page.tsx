"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Decision } from "@/lib/types";
import { Badge, Card, EmptyState, PageHeader, Spinner } from "@/components/ui";

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<Decision[] | null>(null);

  useEffect(() => {
    api
      .listDecisions()
      .then(setDecisions)
      .catch(() => setDecisions([]));
  }, []);

  return (
    <>
      <PageHeader
        title="Decisions"
        description="Structured, evidence-backed conclusions synthesized from completed investigations."
      />

      {decisions === null ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : decisions.length === 0 ? (
        <EmptyState
          title="No decisions yet"
          description="Complete an investigation, then synthesize a decision from it."
        />
      ) : (
        <div className="space-y-4">
          {decisions.map((decision) => (
            <Card key={decision.id} className="p-5">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <Badge tone="accent">confidence {(decision.confidence * 100).toFixed(0)}%</Badge>
                <span className="text-xs text-fg-subtle">
                  {new Date(decision.created_at).toLocaleString()}
                </span>
              </div>
              <p className="text-sm text-fg">{decision.conclusion}</p>
              {decision.recommended_actions.length > 0 && (
                <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-fg-muted">
                  {decision.recommended_actions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              )}
              <Link
                href={`/investigations/${decision.run_id}`}
                className="mt-3 inline-block text-xs font-medium text-accent hover:text-accent-hover"
              >
                View source investigation →
              </Link>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
