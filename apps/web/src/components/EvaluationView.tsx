"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { Dimension, Evaluation } from "@/lib/types";
import { Badge, Card, cx, EngineBadge } from "./ui";

function scoreTone(s: number | null): "ok" | "warn" | "danger" | "neutral" {
  if (s === null) return "neutral";
  return s >= 80 ? "ok" : s >= 50 ? "warn" : "danger";
}

function methodLabel(d: Dimension): string {
  return { rule_based: "rule-based", local_ai: "local AI", requires_local_ai: "needs local AI", not_applicable: "n/a" }[d.method];
}

export function EvaluationView({ e }: { e: Evaluation }) {
  return (
    <Card className="p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[13px] font-semibold">
          Heuristic score: <span className="tabular-nums">{e.score ?? "—"}</span>
          <span className="font-normal text-muted">/100</span>
        </p>
        <EngineBadge engine={e.engine} model={e.model} />
      </div>
      <p className="mb-3 text-xs text-muted">{e.formula}</p>
      <ul className="flex flex-col gap-1.5">
        {e.dimensions.map((d) => <DimensionRow key={d.id} d={d} />)}
      </ul>
      {e.metrics && (
        <p className="mt-3 text-xs text-muted">
          {e.metrics.words} words · {e.metrics.characters} characters · ≈{e.metrics.token_estimate} tokens (estimate, not a tokenizer count)
        </p>
      )}
    </Card>
  );
}

function DimensionRow({ d }: { d: Dimension }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-md border border-border">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left text-xs">
        {open ? <ChevronDown className="size-3.5 text-muted" aria-hidden /> : <ChevronRight className="size-3.5 text-muted" aria-hidden />}
        <span className="w-44 shrink-0 font-medium">{d.name}</span>
        <Badge tone={scoreTone(d.score)}>{d.score === null ? methodLabel(d) : Math.round(d.score)}</Badge>
        <span className="truncate text-muted">{d.summary}</span>
      </button>
      {open && (
        <div className="border-t border-border px-3 py-2 text-xs">
          <p className="mb-1 text-muted">Method: {methodLabel(d)}</p>
          {d.findings.length === 0 ? (
            <p className="text-muted">No issues found by this check.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {d.findings.map((f, i) => (
                <li key={i}>
                  <p>{f.message}</p>
                  {f.evidence.map((ev, j) => <q key={j} className="block font-mono text-[11px] text-muted">{ev}</q>)}
                  {f.fix && <p className="text-muted">Suggested fix: {f.fix}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

export function EvaluationCompare({ a, b, labelA, labelB }: { a: Evaluation; b: Evaluation; labelA: string; labelB: string }) {
  const ids = Array.from(new Set([...a.dimensions, ...b.dimensions].map((d) => d.id)));
  const find = (e: Evaluation, id: string) => e.dimensions.find((d) => d.id === id);
  return (
    <Card className="overflow-x-auto p-3">
      <table className="w-full text-xs">
        <caption className="mb-2 text-left text-muted">Rule-based heuristic diagnostics. Differences show coverage changes, not outcome quality.</caption>
        <thead>
          <tr className="border-b border-border text-left text-muted">
            <th className="py-1.5 font-medium">Dimension</th>
            <th className="py-1.5 text-right font-medium">{labelA}</th>
            <th className="py-1.5 text-right font-medium">{labelB}</th>
            <th className="py-1.5 text-right font-medium">Δ</th>
          </tr>
        </thead>
        <tbody>
          {[{ id: "__score", name: "Aggregate (heuristic)", sa: a.score, sb: b.score }, ...ids.map((id) => ({ id, name: (find(a, id) ?? find(b, id))!.name, sa: find(a, id)?.score ?? null, sb: find(b, id)?.score ?? null }))].map((r) => {
            const delta = r.sa !== null && r.sb !== null ? Math.round(r.sb - r.sa) : null;
            return (
              <tr key={r.id} className={cx("border-b border-border/60", r.id === "__score" && "font-semibold")}>
                <td className="py-1.5">{r.name}</td>
                <td className="py-1.5 text-right tabular-nums">{r.sa === null ? "—" : Math.round(r.sa)}</td>
                <td className="py-1.5 text-right tabular-nums">{r.sb === null ? "—" : Math.round(r.sb)}</td>
                <td className={cx("py-1.5 text-right tabular-nums", delta !== null && delta > 0 && "text-ok", delta !== null && delta < 0 && "text-danger")}>
                  {delta === null ? "—" : delta > 0 ? `+${delta}` : delta}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
