"use client";

import { Check, ChevronDown, ChevronRight, Clock, History, RotateCcw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { formatDate, REQ_KIND_LABELS, REQ_KINDS } from "@/lib/format";
import type { Recommendation, ReqKind } from "@/lib/types";
import { Badge, Button, EngineBadge, Select, Textarea } from "../ui";

export interface ApprovePayload {
  requirement_text?: string;
  requirement_kind?: ReqKind;
  alternative_index?: number;
  note?: string;
}

const PLACEHOLDER = /\[[A-Za-z][^\]]*\s[^\]]+\]/;

export function RecommendationCard({
  rec,
  onApprove,
  onReject,
  onDefer,
  onRestore,
  onSaveEdit,
  busy = false,
}: {
  rec: Recommendation;
  onApprove: (p: ApprovePayload) => void;
  onReject: (note: string) => void;
  onDefer: (note: string) => void;
  onRestore: () => void;
  onSaveEdit: (text: string, kind: ReqKind) => void;
  busy?: boolean;
}) {
  const [expanded, setExpanded] = useState(rec.status === "proposed");
  const [text, setText] = useState(rec.requirement_text);
  const [kind, setKind] = useState<ReqKind>(rec.requirement_kind);
  const [choice, setChoice] = useState<number>(-1); // -1 = main proposal
  const [note, setNote] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  useEffect(() => {
    setText(rec.requirement_text);
    setKind(rec.requirement_kind);
  }, [rec.requirement_text, rec.requirement_kind]);

  const actionable = rec.status === "proposed" || rec.status === "deferred";
  const chosenText = choice >= 0 ? (rec.alternatives[choice]?.requirement_text ?? "") : text;
  const hasPlaceholder = PLACEHOLDER.test(chosenText);
  const edited = text !== rec.requirement_text || kind !== rec.requirement_kind;

  return (
    <article aria-label={rec.title} className="rounded-md border border-border bg-panel">
      <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)} className="flex w-full items-start gap-2 px-3 py-2 text-left">
        {expanded ? <ChevronDown className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden /> : <ChevronRight className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden />}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1">
            <Badge tone={rec.status === "approved" ? "ok" : rec.status === "rejected" ? "danger" : rec.status === "deferred" ? "warn" : "accent"}>{rec.status}</Badge>
            <EngineBadge engine={rec.engine} model={rec.model} />
            <Badge>complexity: {rec.complexity}</Badge>
          </div>
          <p className="mt-1 text-[13px] font-medium">{rec.title}</p>
        </div>
      </button>
      {expanded && (
        <div className="flex flex-col gap-2.5 border-t border-border px-3 py-2.5 text-xs">
          <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1">
            <Item k="Problem" v={rec.problem} />
            <Item k="Why it matters" v={rec.rationale} />
            <Item k="Improvement" v={rec.proposal} />
            <Item k="Benefits" v={rec.benefits} />
            <Item k="Trade-offs" v={rec.tradeoffs} />
            <Item k="Dependencies" v={rec.dependencies} />
            <Item k="Disadvantages" v={rec.disadvantages} />
            <Item k="Verification" v={rec.verification} />
          </dl>

          <div className="rounded-md border border-border bg-panel-2/60 p-2">
            <p className="mb-1.5 font-medium">Requirement added to the specification if approved</p>
            {rec.alternatives.length > 0 && actionable && (
              <fieldset className="mb-2">
                <legend className="mb-1 text-muted">Compare alternatives</legend>
                <div className="grid gap-1.5 md:grid-cols-2">
                  <OptionCard selected={choice === -1} onSelect={() => setChoice(-1)} title="Proposed" text={text} tradeoffs={rec.tradeoffs} />
                  {rec.alternatives.map((a, i) => (
                    <OptionCard key={i} selected={choice === i} onSelect={() => setChoice(i)} title={a.title} text={a.requirement_text} tradeoffs={a.tradeoffs} />
                  ))}
                </div>
              </fieldset>
            )}
            {choice === -1 && actionable ? (
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-2">
                  <label className="text-muted" htmlFor={`kind-${rec.id}`}>Type</label>
                  <Select id={`kind-${rec.id}`} value={kind} onChange={(e) => setKind(e.target.value as ReqKind)} className="h-7 w-44 text-xs">
                    {REQ_KINDS.map((k) => <option key={k} value={k}>{REQ_KIND_LABELS[k]}</option>)}
                  </Select>
                </div>
                <Textarea aria-label="Requirement text" rows={3} value={text} onChange={(e) => setText(e.target.value)} className="text-xs" />
                {edited && (
                  <div className="flex justify-end">
                    <Button size="sm" onClick={() => onSaveEdit(text.trim(), kind)} disabled={!text.trim() || busy}>Save edit as draft</Button>
                  </div>
                )}
              </div>
            ) : (
              !actionable && <p className="text-[12.5px]">{rec.requirement_text}</p>
            )}
            {hasPlaceholder && actionable && (
              <p className="mt-1 text-warn" role="note">Replace the [bracketed placeholder] with your decision before approving.</p>
            )}
          </div>

          {actionable && (
            <Textarea aria-label="Decision note (optional)" rows={1} placeholder="Optional note explaining your decision" value={note} onChange={(e) => setNote(e.target.value)} className="text-xs" />
          )}
          <div className="flex flex-wrap gap-1.5">
            {actionable && (
              <>
                <Button size="sm" variant="primary" icon={<Check className="size-3" />} disabled={busy || hasPlaceholder || !chosenText.trim()}
                  onClick={() => onApprove(choice >= 0 ? { alternative_index: choice, note } : { requirement_text: text.trim(), requirement_kind: kind, note })}>
                  Approve
                </Button>
                <Button size="sm" icon={<X className="size-3" />} disabled={busy} onClick={() => onReject(note)}>Reject</Button>
              </>
            )}
            {rec.status === "proposed" && (
              <Button size="sm" icon={<Clock className="size-3" />} disabled={busy} onClick={() => onDefer(note)}>Defer</Button>
            )}
            {(rec.status === "rejected" || rec.status === "deferred") && (
              <Button size="sm" icon={<RotateCcw className="size-3" />} disabled={busy} onClick={onRestore}>Restore to proposed</Button>
            )}
            <Button size="sm" variant="ghost" icon={<History className="size-3" />} aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}>
              History ({rec.events.length})
            </Button>
          </div>
          {showHistory && (
            <ol className="flex flex-col gap-1 border-l-2 border-border pl-2.5">
              {rec.events.map((e) => (
                <li key={e.id}>
                  <span className="text-muted">{formatDate(e.created_at)}</span> — {e.from_status ? `${e.from_status} → ` : ""}
                  <strong>{e.to_status}</strong>
                  {e.note && <span className="text-muted">: {e.note}</span>}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </article>
  );
}

function Item({ k, v }: { k: string; v: string }) {
  if (!v) return null;
  return (
    <>
      <dt className="text-muted">{k}</dt>
      <dd>{v}</dd>
    </>
  );
}

function OptionCard({ selected, onSelect, title, text, tradeoffs }: { selected: boolean; onSelect: () => void; title: string; text: string; tradeoffs: string }) {
  return (
    <label className={`flex cursor-pointer flex-col gap-1 rounded-md border p-2 ${selected ? "border-accent bg-accent-soft/50" : "border-border bg-panel"}`}>
      <span className="flex items-center gap-1.5 font-medium">
        <input type="radio" checked={selected} onChange={onSelect} className="accent-[var(--accent)]" />
        {title}
      </span>
      <span>{text}</span>
      <span className="text-muted">Trade-offs: {tradeoffs}</span>
    </label>
  );
}
