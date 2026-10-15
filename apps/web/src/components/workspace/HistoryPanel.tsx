"use client";

import { formatDate } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import type { ProjectEvent } from "@/lib/types";
import { EmptyState, ErrorBanner, Spinner } from "../ui";

export function HistoryPanel({ projectId, version }: { projectId: string; version: number }) {
  const ev = useResource<ProjectEvent[]>(`/api/projects/${projectId}/events?limit=200&v=${version}`);
  if (ev.error) return <ErrorBanner message={ev.error} onRetry={ev.reload} />;
  if (!ev.data) return <Spinner />;
  if (ev.data.length === 0) return <EmptyState title="No history yet" />;
  return (
    <ol className="flex flex-col gap-2 border-l-2 border-border pl-3 text-xs">
      {ev.data.map((e) => (
        <li key={e.id}>
          <p className="text-muted">{formatDate(e.created_at)} · {e.kind.replace(/_/g, " ")}</p>
          <p>{e.summary}</p>
        </li>
      ))}
    </ol>
  );
}
