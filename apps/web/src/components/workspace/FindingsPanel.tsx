"use client";

import { ChevronDown, ChevronRight, Play, Sparkles } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { FINDING_KIND_LABELS, relativeTime } from "@/lib/format";
import { useJob } from "@/lib/jobs";
import type { AnalysisOut, AnalysisRun, Finding } from "@/lib/types";
import { useApp } from "../AppContext";
import { useToast } from "../Toast";
import { Badge, Button, EmptyState, EngineBadge, SeverityBadge } from "../ui";
import { AiJobStatus } from "./AiJobStatus";

export function FindingsPanel({
  projectId,
  findings,
  runs,
  dirty,
  onChanged,
}: {
  projectId: string;
  findings: Finding[];
  runs: AnalysisRun[];
  dirty: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const { aiReady, aiUnavailableReason } = useApp();
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState<"open" | "all">("open");
  const ai = useJob((j) => {
    if (j.status === "succeeded") {
      toast(`Local AI analysis: ${String(j.result?.findings ?? 0)} finding(s)`);
      onChanged();
    }
  });

  async function runRules() {
    setBusy(true);
    try {
      const out = await api.post<AnalysisOut>(`/api/projects/${projectId}/analysis`);
      toast(`Rule-based analysis: ${out.findings.filter((f) => f.status === "open").length} open, ${out.new_findings} new, ${out.resolved_findings} resolved`);
      onChanged();
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(f: Finding, status: "open" | "acknowledged" | "dismissed") {
    try {
      await api.patch(`/api/findings/${f.id}`, { status });
      onChanged();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  const visible = findings.filter((f) => show === "all" || f.status === "open" || f.status === "acknowledged");
  const lastRule = runs.find((r) => r.engine === "rule_based");
  const lastAi = runs.find((r) => r.engine === "local_ai");

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" size="sm" icon={<Play className="size-3.5" />} busy={busy} onClick={runRules}>
          Run rule-based analysis
        </Button>
        <Button size="sm" icon={<Sparkles className="size-3.5" />} disabled={!aiReady || ai.running}
          title={aiReady ? "Analyse with the selected local model" : aiUnavailableReason}
          onClick={() => ai.start({ kind: "analysis", project_id: projectId })}>
          Local AI analysis
        </Button>
      </div>
      {dirty && <p className="text-xs text-warn">You have unsaved edits. Analysis uses the last saved version — save first.</p>}
      {!aiReady && <p className="text-xs text-muted">Local AI unavailable: {aiUnavailableReason}</p>}
      <AiJobStatus job={ai.job} running={ai.running} error={ai.error} onCancel={ai.cancel} />
      <p className="text-xs text-muted">
        {lastRule ? `Rule-based: ${relativeTime(lastRule.created_at)} (${lastRule.duration_ms} ms)` : "Not analysed yet."}
        {lastAi && ` · Local AI: ${relativeTime(lastAi.created_at)} (${lastAi.model})`}
      </p>
      <div className="flex gap-2 text-xs">
        {(["open", "all"] as const).map((s) => (
          <button key={s} type="button" aria-pressed={show === s} onClick={() => setShow(s)} className={show === s ? "font-medium text-text" : "text-muted hover:text-text"}>
            {s === "open" ? "Open & acknowledged" : `All (${findings.length})`}
          </button>
        ))}
      </div>
      {visible.length === 0 ? (
        <EmptyState title={findings.length ? "No open findings" : "No findings yet"}>
          {findings.length ? "Resolved and dismissed findings are under “All”." : "Run rule-based analysis to check completeness, ambiguity, contradictions and risks. It works offline."}
        </EmptyState>
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map((f) => (
            <FindingItem key={f.id} f={f} onStatus={(s) => setStatus(f, s)} />
          ))}
        </ul>
      )}
    </div>
  );
}

function FindingItem({ f, onStatus }: { f: Finding; onStatus: (s: "open" | "acknowledged" | "dismissed") => void }) {
  const [open, setOpen] = useState(false);
  const muted = f.status === "dismissed" || f.status === "resolved";
  return (
    <li className={`rounded-md border border-border bg-panel ${muted ? "opacity-60" : ""}`}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex w-full items-start gap-2 px-3 py-2 text-left">
        {open ? <ChevronDown className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden /> : <ChevronRight className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden />}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1">
            <SeverityBadge severity={f.severity} />
            <Badge>{FINDING_KIND_LABELS[f.kind] ?? f.kind}</Badge>
            <EngineBadge engine={f.engine} model={f.model} />
            {f.status !== "open" && <Badge tone={f.status === "resolved" ? "ok" : "neutral"}>{f.status}</Badge>}
          </div>
          <p className="mt-1 text-[13px] font-medium">{f.title}</p>
        </div>
      </button>
      {open && (
        <div className="flex flex-col gap-2 border-t border-border px-3 py-2.5 text-xs">
          <p>{f.explanation}</p>
          {f.evidence.length > 0 && (
            <div>
              <p className="mb-1 font-medium text-muted">Evidence</p>
              <ul className="flex flex-col gap-1">
                {f.evidence.map((e, i) => (
                  <li key={i} className="rounded border border-border bg-panel-2 px-2 py-1">
                    <span className="text-muted">{e.source.startsWith("requirement:") ? "requirement" : e.source}{e.line ? `, line ${e.line}` : ""}: </span>
                    <q className="font-mono text-[11.5px]">{e.quote}</q>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Detail label="Impact" value={f.impact} />
          <Detail label="Proposed solution" value={f.solution} />
          <Detail label="Alternative" value={f.alternative} />
          <Detail label="How to verify" value={f.verification} />
          <p className="text-muted">Confidence: {f.confidence} · Category: {f.category.replace(/_/g, " ")} · ID {f.fingerprint.slice(0, 8)}{f.engine === "rule_based" ? ` · rule ${f.rule_id}` : ""}</p>
          <div className="flex gap-1.5">
            {f.status !== "acknowledged" && f.status !== "resolved" && <Button size="sm" onClick={() => onStatus("acknowledged")}>Acknowledge</Button>}
            {f.status !== "dismissed" && f.status !== "resolved" && <Button size="sm" onClick={() => onStatus("dismissed")}>Dismiss</Button>}
            {(f.status === "dismissed" || f.status === "acknowledged") && <Button size="sm" onClick={() => onStatus("open")}>Reopen</Button>}
          </div>
        </div>
      )}
    </li>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <p>
      <span className="font-medium text-muted">{label}: </span>
      {value}
    </p>
  );
}
