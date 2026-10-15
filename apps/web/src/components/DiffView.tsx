"use client";

import { diffLines } from "diff";
import { useMemo, useState } from "react";
import { cx, Tabs } from "./ui";

export interface DiffLine {
  type: "add" | "del" | "same";
  text: string;
  oldNo: number | null;
  newNo: number | null;
}

export function computeLineDiff(a: string, b: string): { lines: DiffLine[]; added: number; removed: number } {
  const parts = diffLines(a, b);
  const lines: DiffLine[] = [];
  let o = 1;
  let n = 1;
  let added = 0;
  let removed = 0;
  for (const p of parts) {
    const rows = p.value.replace(/\n$/, "").split("\n");
    for (const text of rows) {
      if (p.added) {
        lines.push({ type: "add", text, oldNo: null, newNo: n++ });
        added++;
      } else if (p.removed) {
        lines.push({ type: "del", text, oldNo: o++, newNo: null });
        removed++;
      } else {
        lines.push({ type: "same", text, oldNo: o++, newNo: n++ });
      }
    }
  }
  return { lines, added, removed };
}

export function DiffView({ before, after, beforeLabel, afterLabel }: { before: string; after: string; beforeLabel: string; afterLabel: string }) {
  const { lines, added, removed } = useMemo(() => computeLineDiff(before, after), [before, after]);
  const [mode, setMode] = useState<"unified" | "split">("unified");
  const left = lines.filter((l) => l.type !== "add");
  const right = lines.filter((l) => l.type !== "del");
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted">
          <span className="font-medium text-text">{beforeLabel}</span> → <span className="font-medium text-text">{afterLabel}</span>{" "}
          · <span className="text-ok">+{added}</span> <span className="text-danger">−{removed}</span> lines
        </p>
        <Tabs
          label="Diff layout"
          size="sm"
          value={mode}
          onChange={setMode}
          tabs={[
            { id: "unified", label: "Unified" },
            { id: "split", label: "Side by side" },
          ]}
        />
      </div>
      {added === 0 && removed === 0 ? (
        <p className="rounded-md border border-border px-3 py-4 text-center text-xs text-muted">No differences.</p>
      ) : mode === "unified" ? (
        <pre aria-label="Unified diff" className="max-h-[60vh] overflow-auto rounded-md border border-border bg-panel font-mono text-[12px] leading-5">
          {lines.map((l, i) => (
            <div key={i} className={cx("flex", l.type === "add" && "bg-ok-soft", l.type === "del" && "bg-danger-soft")}>
              <span className="w-10 shrink-0 pr-2 text-right text-muted select-none">{l.oldNo ?? ""}</span>
              <span className="w-10 shrink-0 pr-2 text-right text-muted select-none">{l.newNo ?? ""}</span>
              <span className={cx("w-4 shrink-0 select-none", l.type === "add" ? "text-ok" : l.type === "del" ? "text-danger" : "text-muted")}>
                {l.type === "add" ? "+" : l.type === "del" ? "−" : " "}
              </span>
              <span className="pr-3 whitespace-pre-wrap">{l.text || " "}</span>
            </div>
          ))}
        </pre>
      ) : (
        <div className="grid max-h-[60vh] grid-cols-2 overflow-auto rounded-md border border-border font-mono text-[12px] leading-5">
          {[left, right].map((col, ci) => (
            <pre key={ci} className={cx("min-w-0", ci === 0 && "border-r border-border")}>
              {col.map((l, i) => (
                <div key={i} className={cx("flex", l.type === "add" && "bg-ok-soft", l.type === "del" && "bg-danger-soft")}>
                  <span className="w-9 shrink-0 pr-2 text-right text-muted select-none">{ci === 0 ? l.oldNo : l.newNo}</span>
                  <span className="pr-2 whitespace-pre-wrap">{l.text || " "}</span>
                </div>
              ))}
            </pre>
          ))}
        </div>
      )}
    </div>
  );
}
