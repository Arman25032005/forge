"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { AgentRun, Decision } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  ErrorBanner,
  PageHeader,
  Spinner,
  statusTone,
} from "@/components/ui";

export default function InvestigationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [synthesisError, setSynthesisError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRun(id)
      .then((r) => {
        setRun(r);
        return api
          .getDecisionForRun(id)
          .then(setDecision)
          .catch(() => setDecision(null));
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
      });
  }, [id]);

  async function handleSynthesize() {
    setSynthesisError(null);
    setSynthesizing(true);
    try {
      const d = await api.synthesizeDecision(id);
      setDecision(d);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setSynthesisError("No reasoning model is configured for this deployment.");
      } else if (err instanceof ApiError) {
        setSynthesisError(typeof err.detail === "string" ? err.detail : "Could not synthesize a decision.");
      } else {
        setSynthesisError("Could not reach the server.");
      }
    } finally {
      setSynthesizing(false);
    }
  }

  if (notFound) {
    return (
      <div className="py-16 text-center text-sm text-fg-muted">
        Investigation not found.{" "}
        <Link href="/investigations" className="text-accent hover:text-accent-hover">
          Back to investigations
        </Link>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  return (
    <>
      <Link href="/investigations" className="mb-4 inline-block text-xs text-fg-muted hover:text-fg">
        ← All investigations
      </Link>
      <PageHeader
        title={run.question}
        actions={<Badge tone={statusTone(run.status)}>{run.status.replace(/_/g, " ")}</Badge>}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-fg">Investigation trace</h2>
          <ol className="relative space-y-4 border-l border-border pl-6">
            {run.steps.map((step) => (
              <li key={step.step_index} className="relative">
                <span className="absolute -left-[29px] top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 border-bg bg-accent" />
                <Card className="p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-mono text-xs font-medium text-accent">
                      {step.tool_name ?? "unknown tool"}
                    </span>
                    <span className="text-xs text-fg-subtle">Step {step.step_index + 1}</span>
                  </div>
                  {step.thought && <p className="mb-2 text-sm text-fg-muted italic">&ldquo;{step.thought}&rdquo;</p>}
                  <JsonBlock label="Input" value={step.tool_input} />
                  <JsonBlock label="Result" value={step.tool_output} />
                </Card>
              </li>
            ))}
            {run.status === "running" && (
              <li className="relative">
                <span className="animate-pulse-ring absolute -left-[29px] top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 border-bg bg-accent" />
                <p className="pt-0.5 text-sm text-fg-muted">Thinking…</p>
              </li>
            )}
          </ol>

          {run.final_answer && (
            <Card className="mt-4 border-accent/30 bg-accent-soft/40 p-4">
              <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-accent">
                Final answer
              </h3>
              <p className="whitespace-pre-wrap text-sm text-fg">{run.final_answer}</p>
            </Card>
          )}

          {run.status === "failed" && run.error && (
            <div className="mt-4">
              <ErrorBanner message={`Investigation failed: ${run.error}`} />
            </div>
          )}
          {run.status === "max_steps_exceeded" && (
            <div className="mt-4">
              <ErrorBanner message="The agent reached its step limit before reaching a final answer." />
            </div>
          )}
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold text-fg">Decision</h2>
          {decision ? (
            <Card className="space-y-3 p-4">
              <div className="flex items-center justify-between">
                <Badge tone="accent">confidence {(decision.confidence * 100).toFixed(0)}%</Badge>
              </div>
              <p className="text-sm text-fg">{decision.conclusion}</p>
              {decision.evidence.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium text-fg-muted">Evidence</p>
                  <ul className="space-y-1">
                    {decision.evidence.map((e, i) => (
                      <li key={i} className="text-xs text-fg-subtle">
                        Step {e.step_index + 1}: {e.summary}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {decision.recommended_actions.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium text-fg-muted">Recommended actions</p>
                  <ul className="list-inside list-disc space-y-1 text-xs text-fg">
                    {decision.recommended_actions.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          ) : run.status === "completed" ? (
            <Card className="p-4">
              {synthesisError && (
                <div className="mb-3">
                  <ErrorBanner message={synthesisError} />
                </div>
              )}
              <p className="mb-3 text-sm text-fg-muted">
                Turn this investigation into a structured, evidence-backed conclusion.
              </p>
              <Button onClick={handleSynthesize} loading={synthesizing} className="w-full">
                Synthesize decision
              </Button>
            </Card>
          ) : (
            <Card className="p-4">
              <p className="text-sm text-fg-subtle">
                Available once the investigation completes.
              </p>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined) return null;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <details className="mt-2 group">
      <summary className="cursor-pointer text-xs font-medium text-fg-muted group-open:text-fg">
        {label}
      </summary>
      <pre className="mt-1.5 max-h-64 overflow-auto rounded-lg bg-bg-inset p-3 font-mono text-xs text-fg-muted">
        {text}
      </pre>
    </details>
  );
}
