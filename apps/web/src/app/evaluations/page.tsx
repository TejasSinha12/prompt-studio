"use client";

import { Gauge } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { EvaluationCompare, EvaluationView } from "@/components/EvaluationView";
import { Badge, Button, Card, EmptyState, EngineBadge, ErrorBanner, PageHeader, Spinner, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import type { Evaluation } from "@/lib/types";

export default function EvaluationsPage() {
  const list = useResource<Evaluation[]>("/api/evaluations?limit=100");
  const [selected, setSelected] = useState<string[]>([]);
  const [scratch, setScratch] = useState("");
  const [scratchEval, setScratchEval] = useState<Evaluation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const evs = list.data ?? [];
  const chosen = selected.map((id) => evs.find((e) => e.id === id)).filter(Boolean) as Evaluation[];

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s.slice(-1), id]));
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <PageHeader title="Evaluations" description="Transparent quality diagnostics. Scores are heuristics documented in each result — not predictions of success." />
      {list.error && <ErrorBanner message={list.error} onRetry={list.reload} />}
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Card>
          <div className="border-b border-border px-4 py-2 text-xs text-muted">Select two evaluations to compare.</div>
          {!list.data ? <div className="p-4"><Spinner /></div> : evs.length === 0 ? (
            <EmptyState icon={<Gauge className="size-6" />} title="No evaluations yet">Evaluate versions from the Versions tab of a prompt.</EmptyState>
          ) : (
            <ul className="max-h-[70vh] divide-y divide-border overflow-y-auto">
              {evs.map((e) => (
                <li key={e.id} className="flex items-center gap-3 px-4 py-2 text-[13px]">
                  <input type="checkbox" aria-label={`Select evaluation of ${e.prompt_title} v${e.version_number}`} checked={selected.includes(e.id!)} onChange={() => toggle(e.id!)} />
                  <div className="min-w-0 flex-1">
                    <Link href={`/library/${e.prompt_id}`} className="font-medium hover:text-accent">{e.prompt_title} <span className="text-muted">v{e.version_number}</span></Link>
                    <p className="text-xs text-muted">{formatDate(e.created_at)}</p>
                  </div>
                  <EngineBadge engine={e.engine} model={e.model} />
                  <Badge tone={e.score === null ? "neutral" : e.score >= 80 ? "ok" : e.score >= 50 ? "warn" : "danger"}>{e.score ?? "—"}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <div className="flex flex-col gap-3">
          {chosen.length === 2 ? (
            <EvaluationCompare a={chosen[0]!} b={chosen[1]!} labelA={`${chosen[0]!.prompt_title} v${chosen[0]!.version_number}`} labelB={`${chosen[1]!.prompt_title} v${chosen[1]!.version_number}`} />
          ) : chosen.length === 1 ? (
            <EvaluationView e={chosen[0]!} />
          ) : (
            <Card className="p-4">
              <h2 className="mb-1 text-[13px] font-semibold">Quick check</h2>
              <p className="mb-2 text-xs text-muted">Paste any prompt to run rule-based diagnostics. Nothing is stored.</p>
              <Textarea aria-label="Prompt to evaluate" rows={8} value={scratch} onChange={(e) => setScratch(e.target.value)} className="font-mono text-xs" />
              <Button size="sm" className="mt-2" disabled={!scratch.trim()} onClick={async () => {
                try { setErr(null); setScratchEval(await api.post<Evaluation>("/api/evaluate-text", { content: scratch, coding: true })); } catch (e) { setErr(errorMessage(e)); }
              }}>Evaluate</Button>
              {err && <p className="mt-2 text-xs text-danger">{err}</p>}
            </Card>
          )}
          {chosen.length === 0 && scratchEval && <EvaluationView e={scratchEval} />}
        </div>
      </div>
    </div>
  );
}
