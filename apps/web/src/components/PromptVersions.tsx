"use client";

import { Gauge, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import { useJob } from "@/lib/jobs";
import type { Evaluation, PromptDetail, Version } from "@/lib/types";
import { useApp } from "./AppContext";
import { DiffView } from "./DiffView";
import { EvaluationCompare, EvaluationView } from "./EvaluationView";
import { Markdown } from "./Markdown";
import { useToast } from "./Toast";
import { Badge, Button, Card, EmptyState, EngineBadge, ErrorBanner, Spinner, Tabs } from "./ui";
import { AiJobStatus } from "./workspace/AiJobStatus";

/** Version history for one prompt: view, diff any two versions, restore, evaluate and compare. */
export function PromptVersions({ promptId, refreshKey = 0, onChanged }: { promptId: string; refreshKey?: number; onChanged?: () => void }) {
  const toast = useToast();
  const { aiReady, aiUnavailableReason } = useApp();
  const detail = useResource<PromptDetail>(`/api/prompts/${promptId}?k=${refreshKey}`);
  const [a, setA] = useState<string | null>(null); // older
  const [b, setB] = useState<string | null>(null); // newer
  const [va, setVa] = useState<Version | null>(null);
  const [vb, setVb] = useState<Version | null>(null);
  const [view, setView] = useState<"diff" | "content" | "evaluation">("diff");
  const [evA, setEvA] = useState<Evaluation | null>(null);
  const [evB, setEvB] = useState<Evaluation | null>(null);
  const [busy, setBusy] = useState(false);
  const ai = useJob((j) => {
    if (j.status === "succeeded") {
      toast("Local AI feasibility evaluation stored");
      void loadEvals();
    }
  });

  const versions = detail.data?.versions ?? [];
  useEffect(() => {
    if (versions.length && (!b || !versions.some((v) => v.id === b))) {
      setB(versions[0]!.id);
      setA(versions[1]?.id ?? versions[0]!.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.data]);

  useEffect(() => {
    if (a) void api.get<Version>(`/api/prompts/${promptId}/versions/${a}`).then(setVa).catch(() => setVa(null));
  }, [a, promptId]);
  useEffect(() => {
    if (b) void api.get<Version>(`/api/prompts/${promptId}/versions/${b}`).then(setVb).catch(() => setVb(null));
  }, [b, promptId]);

  async function loadEvals() {
    const latest = async (id: string | null) => (id ? ((await api.get<Evaluation[]>(`/api/prompt-versions/${id}/evaluations`)).find((e) => e.engine === "rule_based") ?? null) : null);
    const [x, y] = await Promise.all([latest(a), latest(b)]);
    setEvA(x);
    setEvB(y);
  }
  useEffect(() => {
    if (view === "evaluation") void loadEvals().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, a, b]);

  async function restore(id: string, n: number) {
    setBusy(true);
    try {
      await api.post(`/api/prompts/${promptId}/versions/${id}/restore`);
      toast(`Restored v${n} as a new version`);
      await detail.reload();
      onChanged?.();
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function evaluate(ids: (string | null)[]) {
    setBusy(true);
    try {
      for (const id of new Set(ids.filter(Boolean) as string[])) await api.post(`/api/prompt-versions/${id}/evaluate`);
      await loadEvals();
      setView("evaluation");
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  }

  if (detail.error) return <ErrorBanner message={detail.error} onRetry={detail.reload} />;
  if (!detail.data) return <Spinner />;
  if (versions.length === 0) return <EmptyState title="No versions yet" />;
  const current = detail.data.current_version_id;
  const num = (id: string | null) => versions.find((v) => v.id === id)?.number;

  return (
    <div className="grid gap-3 lg:grid-cols-[300px_1fr]">
      <Card className="max-h-[70vh] overflow-y-auto">
        <div className="sticky top-0 border-b border-border bg-panel px-3 py-2 text-xs text-muted">
          {versions.length} version(s). Select <strong>A</strong> (base) and <strong>B</strong> (compare).
        </div>
        <ul className="divide-y divide-border">
          {versions.map((v) => (
            <li key={v.id} className={`px-3 py-2 text-xs ${v.id === b ? "bg-accent-soft/40" : ""}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[13px] font-medium">
                  v{v.number} {v.id === current && <Badge tone="ok">current</Badge>}
                </span>
                <div className="flex gap-1">
                  <button type="button" aria-pressed={a === v.id} aria-label={`Use v${v.number} as A`} onClick={() => setA(v.id)} className={`rounded border px-1.5 ${a === v.id ? "border-accent text-accent" : "border-border text-muted"}`}>A</button>
                  <button type="button" aria-pressed={b === v.id} aria-label={`Use v${v.number} as B`} onClick={() => setB(v.id)} className={`rounded border px-1.5 ${b === v.id ? "border-accent text-accent" : "border-border text-muted"}`}>B</button>
                </div>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1">
                <Badge>{v.variant}</Badge>
                <EngineBadge engine={v.generator} model={v.model} />
              </div>
              <p className="mt-1 text-muted">{v.change_summary || "—"}</p>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-muted">{formatDate(v.created_at)}</span>
                {v.id !== current && (
                  <Button size="sm" variant="ghost" icon={<RotateCcw className="size-3" />} disabled={busy} onClick={() => restore(v.id, v.number)}>
                    Restore
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </Card>
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Tabs label="Version view" value={view} onChange={setView} tabs={[{ id: "diff", label: "Diff A → B" }, { id: "content", label: "Content (B)" }, { id: "evaluation", label: "Quality" }]} />
          <div className="flex gap-1.5">
            <Button size="sm" icon={<Gauge className="size-3" />} busy={busy} onClick={() => evaluate([a, b])}>Evaluate A & B</Button>
            <Button size="sm" icon={<Sparkles className="size-3" />} disabled={!aiReady || ai.running || !b} title={aiReady ? "Judgment-based feasibility via local model" : aiUnavailableReason}
              onClick={() => b && ai.start({ kind: "evaluate", version_id: b })}>
              AI feasibility (B)
            </Button>
          </div>
        </div>
        <AiJobStatus job={ai.job} running={ai.running} error={ai.error} onCancel={ai.cancel} />
        {view === "diff" && va && vb && <DiffView before={va.content} after={vb.content} beforeLabel={`v${va.number}`} afterLabel={`v${vb.number}`} />}
        {view === "content" && vb && (
          <Card className="max-h-[70vh] overflow-y-auto p-4"><Markdown content={vb.content} /></Card>
        )}
        {view === "evaluation" && (
          evA || evB ? (
            a !== b && evA && evB ? <EvaluationCompare a={evA} b={evB} labelA={`v${num(a)}`} labelB={`v${num(b)}`} /> : <EvaluationView e={(evB ?? evA)!} />
          ) : (
            <EmptyState title="Not evaluated yet" action={<Button size="sm" onClick={() => evaluate([a, b])}>Evaluate A & B</Button>}>Rule-based diagnostics run locally in milliseconds.</EmptyState>
          )
        )}
        {view === "evaluation" && b && <AiEvaluations versionId={b} refresh={ai.job?.status} />}
      </div>
    </div>
  );
}

function AiEvaluations({ versionId, refresh }: { versionId: string; refresh?: string }) {
  const evs = useResource<Evaluation[]>(`/api/prompt-versions/${versionId}/evaluations?r=${refresh ?? ""}`);
  const ai = (evs.data ?? []).filter((e) => e.engine === "local_ai");
  if (ai.length === 0) return null;
  const e = ai[0]!;
  const d = e.dimensions[0];
  return (
    <Card className="p-3 text-xs">
      <p className="mb-1 flex items-center gap-2 font-medium">Implementation feasibility (judgment) <EngineBadge engine="local_ai" model={e.model} /></p>
      <p>Score {d?.score ?? "—"}/100 — {d?.summary}</p>
      <p className="mt-1 text-muted">A model's judgment, not a measurement or probability of success. Evaluated {formatDate(e.created_at)}.</p>
      {d?.findings.map((f, i) => <p key={i} className="mt-1">• {f.message}{f.fix && <span className="text-muted"> — fix: {f.fix}</span>}</p>)}
    </Card>
  );
}
