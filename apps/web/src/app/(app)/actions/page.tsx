"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { ActionItem } from "@/lib/types";
import { can } from "@/lib/types";
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
  statusTone,
} from "@/components/ui";

const ACTION_TYPES = [
  { value: "flag_customer_at_risk", label: "Flag customer at risk", needsCustomer: true },
  { value: "create_support_ticket", label: "Create support ticket", needsCustomer: true },
  { value: "manual_task", label: "Manual task (human follow-up)", needsCustomer: false },
];

export default function ActionsPage() {
  const { user } = useAuth();
  const [actions, setActions] = useState<ActionItem[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  function load() {
    api
      .listActions()
      .then(setActions)
      .catch(() => setActions([]));
  }
  useEffect(load, []);

  async function transition(id: string, t: "approve" | "reject" | "execute") {
    setError(null);
    setBusyId(id);
    try {
      await api.transitionAction(id, t);
      load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError("You can't approve your own proposed action — ask a teammate to review it.");
      } else if (err instanceof ApiError) {
        setError(typeof err.detail === "string" ? err.detail : `Could not ${t} this action.`);
      } else {
        setError("Could not reach the server.");
      }
    } finally {
      setBusyId(null);
    }
  }

  const canPropose = can(user?.role, "action.propose");
  const canExecute = can(user?.role, "action.execute");

  return (
    <>
      <PageHeader
        title="Actions"
        description="Proposed actions require approval from a different user before they execute."
        actions={
          canPropose && (
            <Button onClick={() => setShowForm((s) => !s)} variant={showForm ? "secondary" : "primary"}>
              {showForm ? "Cancel" : "Propose action"}
            </Button>
          )
        }
      />

      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      {showForm && (
        <div className="mb-6">
          <ProposeActionForm
            onProposed={() => {
              setShowForm(false);
              load();
            }}
          />
        </div>
      )}

      {actions === null ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : actions.length === 0 ? (
        <EmptyState title="No actions yet" description="Proposed actions will appear here." />
      ) : (
        <Card>
          <ul className="divide-y divide-border">
            {actions.map((action) => {
              const isOwnProposal = action.proposed_by === user?.id;
              return (
                <li key={action.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-fg-subtle">{action.action_type}</span>
                      <Badge tone={statusTone(action.status)}>{action.status}</Badge>
                    </div>
                    <p className="mt-1 truncate text-sm text-fg">{action.description}</p>
                    {action.result && (
                      <p className="mt-1 truncate text-xs text-fg-subtle">
                        Result: {JSON.stringify(action.result)}
                      </p>
                    )}
                  </div>
                  {action.status === "proposed" && canExecute && (
                    <div className="flex shrink-0 gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={busyId === action.id}
                        disabled={isOwnProposal}
                        title={isOwnProposal ? "You proposed this — a teammate must approve it" : undefined}
                        onClick={() => transition(action.id, "reject")}
                      >
                        Reject
                      </Button>
                      <Button
                        size="sm"
                        loading={busyId === action.id}
                        disabled={isOwnProposal}
                        title={isOwnProposal ? "You proposed this — a teammate must approve it" : undefined}
                        onClick={() => transition(action.id, "approve")}
                      >
                        Approve
                      </Button>
                    </div>
                  )}
                  {action.status === "approved" && canExecute && (
                    <Button size="sm" loading={busyId === action.id} onClick={() => transition(action.id, "execute")}>
                      Execute
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </>
  );
}

function ProposeActionForm({ onProposed }: { onProposed: () => void }) {
  const [actionType, setActionType] = useState(ACTION_TYPES[0].value);
  const [description, setDescription] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [subject, setSubject] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const meta = ACTION_TYPES.find((t) => t.value === actionType)!;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const parameters: Record<string, unknown> = {};
      if (meta.needsCustomer) parameters.customer_id = customerId.trim();
      if (actionType === "create_support_ticket") parameters.subject = subject.trim();
      if (actionType === "manual_task" && note.trim()) parameters.note = note.trim();

      await api.proposeAction({ action_type: actionType, description: description.trim(), parameters });
      setDescription("");
      setCustomerId("");
      setSubject("");
      setNote("");
      onProposed();
    } catch (err) {
      setError(err instanceof ApiError && typeof err.detail === "string" ? err.detail : "Could not propose this action.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="p-5">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        {error && <ErrorBanner message={error} />}
        <div>
          <Label>Action type</Label>
          <select
            value={actionType}
            onChange={(e) => setActionType(e.target.value)}
            className="w-full rounded-lg border border-border-strong bg-bg-inset px-3 py-2 text-sm text-fg outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          >
            {ACTION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label>Description (for the approver)</Label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            required
          />
        </div>
        {meta.needsCustomer && (
          <div>
            <Label>Customer ID</Label>
            <Input
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              placeholder="UUID — find one via the data explorer"
              required
            />
          </div>
        )}
        {actionType === "create_support_ticket" && (
          <div>
            <Label>Ticket subject</Label>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} required />
          </div>
        )}
        {actionType === "manual_task" && (
          <div>
            <Label>Note (optional)</Label>
            <Input value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        )}
        <Button type="submit" loading={submitting} className="self-start">
          Propose
        </Button>
      </form>
    </Card>
  );
}
