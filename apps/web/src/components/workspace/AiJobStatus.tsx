"use client";

import { Loader2, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { elapsed } from "@/lib/jobs";
import type { Job } from "@/lib/types";
import { Button } from "../ui";

/** Progress line for a running local-AI job with a cancel button. */
export function AiJobStatus({ job, running, error, onCancel }: { job: Job | null; running: boolean; error: string | null; onCancel: () => void }) {
  const [, tick] = useState(0);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [running]);
  if (running && job)
    return (
      <div role="status" className="flex items-center justify-between gap-2 rounded-md border border-accent/40 bg-accent-soft px-3 py-2 text-xs text-accent">
        <span className="flex items-center gap-2">
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
          {job.status === "queued" ? "Queued — waiting for another local-AI job" : `Local model ${job.model ?? ""} working`} · {elapsed(job)}
        </span>
        <Button size="sm" icon={<Square className="size-3" />} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    );
  if (job?.status === "cancelled") return <p className="text-xs text-muted">Local-AI job cancelled.</p>;
  if (error)
    return (
      <p role="alert" className="rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-xs text-danger">
        Local AI failed: {error} Rule-based features are unaffected.
      </p>
    );
  return null;
}
