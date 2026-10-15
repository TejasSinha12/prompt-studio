"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { REQ_KIND_LABELS, REQ_KINDS } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import { useJob } from "@/lib/jobs";
import type { ClarificationQuestion, ReqKind } from "@/lib/types";
import { useApp } from "../AppContext";
import { useToast } from "../Toast";
import { Button, EmptyState, EngineBadge, Select, Spinner, Textarea } from "../ui";
import { AiJobStatus } from "./AiJobStatus";

export function ClarifyPanel({ projectId, version, onAnswered }: { projectId: string; version: number; onAnswered: () => void }) {
  const toast = useToast();
  const { aiReady, aiUnavailableReason } = useApp();
  const rule = useResource<ClarificationQuestion[]>(`/api/projects/${projectId}/clarifications?v=${version}`);
  const [aiQs, setAiQs] = useState<ClarificationQuestion[]>([]);
  const ai = useJob((j) => {
    if (j.status === "succeeded") setAiQs((j.result?.questions as ClarificationQuestion[]) ?? []);
  });
  const all = [...(rule.data ?? []), ...aiQs];
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted">Answer focused questions; each answer becomes a confirmed requirement. Rule-based questions come from open findings.</p>
      <Button size="sm" icon={<Sparkles className="size-3.5" />} disabled={!aiReady || ai.running} title={aiReady ? undefined : aiUnavailableReason}
        onClick={() => ai.start({ kind: "clarify", project_id: projectId })} className="self-start">
        Ask local AI for questions
      </Button>
      <AiJobStatus job={ai.job} running={ai.running} error={ai.error} onCancel={ai.cancel} />
      {rule.loading && !rule.data ? <Spinner /> : all.length === 0 ? (
        <EmptyState title="No open questions">Run an analysis first; questions are derived from open findings.</EmptyState>
      ) : (
        all.map((q) => (
          <QuestionItem key={q.id} q={q} onSubmit={async (answer, kind) => {
            try {
              await api.post(`/api/projects/${projectId}/clarifications`, { question: q.question, answer, kind });
              toast("Answer added as a confirmed requirement");
              setAiQs((xs) => xs.filter((x) => x.id !== q.id));
              onAnswered();
              await rule.reload();
            } catch (e) {
              toast(errorMessage(e), "error");
            }
          }} />
        ))
      )}
    </div>
  );
}

function QuestionItem({ q, onSubmit }: { q: ClarificationQuestion; onSubmit: (answer: string, kind: ReqKind) => Promise<void> }) {
  const [answer, setAnswer] = useState("");
  const [kind, setKind] = useState<ReqKind>(q.suggested_kind);
  const [busy, setBusy] = useState(false);
  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border bg-panel p-2.5 text-xs">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] font-medium">{q.question}</p>
        <EngineBadge engine={q.source} />
      </div>
      {q.why && <p className="text-muted">{q.why}</p>}
      <Textarea aria-label={`Answer: ${q.question}`} rows={2} value={answer} onChange={(e) => setAnswer(e.target.value)} className="text-xs" />
      <div className="flex items-center justify-end gap-2">
        <Select aria-label="Save answer as" value={kind} onChange={(e) => setKind(e.target.value as ReqKind)} className="h-7 w-44 text-xs">
          {REQ_KINDS.map((k) => <option key={k} value={k}>{REQ_KIND_LABELS[k]}</option>)}
        </Select>
        <Button size="sm" variant="primary" busy={busy} disabled={!answer.trim()}
          onClick={async () => { setBusy(true); await onSubmit(answer.trim(), kind); setBusy(false); setAnswer(""); }}>
          Add answer
        </Button>
      </div>
    </div>
  );
}
