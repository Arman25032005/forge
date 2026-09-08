"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { AgentRun } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBanner,
  PageHeader,
  Spinner,
  Textarea,
  statusTone,
} from "@/components/ui";

const EXAMPLES = [
  "Why might some customers be at risk of churning?",
  "Which customers have overdue invoices?",
  "Are there any customers with a high volume of support tickets?",
];

export default function InvestigationsPage() {
  const router = useRouter();
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api
      .listRuns()
      .then(setRuns)
      .catch(() => setRuns([]));
  }

  useEffect(load, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      const run = await api.createRun(question.trim());
      router.push(`/investigations/${run.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setError(
          "No reasoning model is configured for this deployment (FORGE_GROQ_API_KEY / FORGE_ANTHROPIC_API_KEY unset).",
        );
      } else if (err instanceof ApiError) {
        setError(typeof err.detail === "string" ? err.detail : "Could not start the investigation.");
      } else {
        setError("Could not reach the server.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Investigations"
        description="Ask a business question; the agent gathers evidence from your own data before answering."
      />

      <Card className="mb-8 p-5">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {error && <ErrorBanner message={error} />}
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Why might some customers be at risk of churning?"
            rows={2}
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setQuestion(ex)}
                  className="rounded-full border border-border-strong px-2.5 py-1 text-xs text-fg-muted hover:border-accent hover:text-accent"
                >
                  {ex}
                </button>
              ))}
            </div>
            <Button type="submit" loading={submitting} disabled={!question.trim()}>
              {submitting ? "Investigating…" : "Start investigation"}
            </Button>
          </div>
          {submitting && (
            <p className="text-xs text-fg-subtle">
              The agent is querying data and reasoning step by step — this can take up to a minute.
            </p>
          )}
        </form>
      </Card>

      {runs === null ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : runs.length === 0 ? (
        <EmptyState
          title="No investigations yet"
          description="Ask your first question above to see the agent in action."
        />
      ) : (
        <Card>
          <ul className="divide-y divide-border">
            {runs.map((run) => (
              <li key={run.id}>
                <a
                  href={`/investigations/${run.id}`}
                  className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-bg-inset"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-fg">{run.question}</p>
                    <p className="mt-0.5 text-xs text-fg-subtle">
                      {new Date(run.created_at).toLocaleString()} · {run.steps.length} step
                      {run.steps.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <Badge tone={statusTone(run.status)}>{run.status.replace(/_/g, " ")}</Badge>
                </a>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
