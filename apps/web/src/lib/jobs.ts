"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";
import type { Job, JobKind } from "./types";

export interface JobRequest {
  kind: JobKind;
  project_id?: string;
  version_id?: string;
  variant?: string;
  profile_id?: string | null;
  content?: string;
}

/** Start a local-AI job, poll until it finishes, allow cancellation. */
export function useJob(onDone?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  const stop = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  const poll = useCallback((id: string) => {
    timer.current = setTimeout(async () => {
      try {
        const j = await api.get<Job>(`/api/ai/jobs/${id}`);
        setJob(j);
        if (j.status === "queued" || j.status === "running") poll(id);
        else doneRef.current?.(j);
      } catch (e) {
        setError(errorMessage(e));
      }
    }, 800);
  }, []);

  const start = useCallback(
    async (req: JobRequest) => {
      stop();
      setError(null);
      try {
        const j = await api.post<Job>("/api/ai/jobs", req);
        setJob(j);
        poll(j.id);
      } catch (e) {
        setError(errorMessage(e));
      }
    },
    [poll],
  );

  const cancel = useCallback(async () => {
    if (!job) return;
    try {
      await api.del(`/api/ai/jobs/${job.id}`);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [job]);

  useEffect(() => stop, []);

  const running = job?.status === "queued" || job?.status === "running";
  const failed = job?.status === "failed" ? job.error : null;
  return { job, running, start, cancel, error: error ?? failed, reset: () => { stop(); setJob(null); setError(null); } };
}

export function elapsed(job: Job | null): string {
  if (!job?.started_at) return "";
  const end = job.finished_at ? new Date(job.finished_at).getTime() : Date.now();
  return `${Math.round((end - new Date(job.started_at).getTime()) / 1000)}s`;
}
