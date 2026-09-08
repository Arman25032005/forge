"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { can } from "@/lib/types";
import type { DocumentItem } from "@/lib/types";
import {
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

export default function DocumentsPage() {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[] | null>(null);
  const [showForm, setShowForm] = useState(false);

  function load() {
    api
      .listDocuments()
      .then(setDocuments)
      .catch(() => setDocuments([]));
  }
  useEffect(load, []);

  const canWrite = can(user?.role, "document.write");

  return (
    <>
      <PageHeader
        title="Documents"
        description="Ingested documents are chunked and embedded automatically, so they're searchable by the agent."
        actions={
          canWrite && (
            <Button onClick={() => setShowForm((s) => !s)} variant={showForm ? "secondary" : "primary"}>
              {showForm ? "Cancel" : "Ingest document"}
            </Button>
          )
        }
      />

      {showForm && (
        <div className="mb-6">
          <IngestForm
            onIngested={() => {
              setShowForm(false);
              load();
            }}
          />
        </div>
      )}

      {documents === null ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : documents.length === 0 ? (
        <EmptyState title="No documents yet" description="Ingest a document to make it searchable." />
      ) : (
        <Card>
          <ul className="divide-y divide-border">
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-fg">{doc.title}</p>
                  <p className="text-xs text-fg-subtle">
                    {doc.source} · {new Date(doc.created_at).toLocaleString()}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

function IngestForm({ onIngested }: { onIngested: () => void }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.ingestDocument(title.trim(), content.trim());
      setTitle("");
      setContent("");
      onIngested();
    } catch (err) {
      setError(err instanceof ApiError && typeof err.detail === "string" ? err.detail : "Could not ingest document.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="p-5">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        {error && <ErrorBanner message={error} />}
        <div>
          <Label>Title</Label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </div>
        <div>
          <Label>Content</Label>
          <Textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6} required />
        </div>
        <Button type="submit" loading={submitting} className="self-start">
          Ingest
        </Button>
      </form>
    </Card>
  );
}
