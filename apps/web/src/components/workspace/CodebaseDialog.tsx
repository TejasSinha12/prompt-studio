"use client";

import { FolderSearch, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { Markdown } from "../Markdown";
import { Badge, Button, Dialog, Field, Input, Notice } from "../ui";

interface Entry {
  path: string;
  size: number;
  included: boolean;
  reason: string;
  suggested: boolean;
}
interface ScanResult {
  root: string;
  entries: Entry[];
  truncated: boolean;
  stack: string[];
  dependencies: Record<string, string[]>;
  conventions: string[];
  test_dirs: string[];
}
interface SummaryResult {
  markdown: string;
  files_included: string[];
  files_skipped: Record<string, string>;
  redactions: number;
  total_bytes: number;
}

const MAX_SELECTED = 40;

/** Read-only, user-initiated scan of a local directory to build codebase context. */
export function CodebaseDialog({ open, onClose, onInsert }: { open: boolean; onClose: () => void; onInsert: (markdown: string) => void }) {
  const [path, setPath] = useState("");
  const [excludes, setExcludes] = useState("");
  const [maxKb, setMaxKb] = useState(100);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [showExcluded, setShowExcluded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const body = () => ({ path: path.trim(), max_file_kb: maxKb, extra_excludes: excludes.split(",").map((s) => s.trim()).filter(Boolean) });

  const files = useMemo(() => (scan?.entries ?? []).filter((e) => !e.path.endsWith("/")), [scan]);
  const included = files.filter((e) => e.included);
  const excluded = (scan?.entries ?? []).filter((e) => !e.included);

  async function doScan() {
    setBusy(true);
    setErr(null);
    setSummary(null);
    try {
      const r = await api.post<ScanResult>("/api/codebase/scan", body());
      setScan(r);
      setSelected(new Set(r.entries.filter((e) => e.suggested).slice(0, MAX_SELECTED).map((e) => e.path)));
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function doSummary() {
    setBusy(true);
    setErr(null);
    try {
      setSummary(await api.post<SummaryResult>("/api/codebase/summary", { ...body(), files: Array.from(selected) }));
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function toggle(p: string) {
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(p)) n.delete(p);
      else if (n.size < MAX_SELECTED) n.add(p);
      return n;
    });
  }

  return (
    <Dialog open={open} onClose={onClose} title="Codebase context from a local directory" wide
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          {summary ? (
            <Button variant="primary" onClick={() => { onInsert(summary.markdown); onClose(); }}>Insert into “Existing codebase”</Button>
          ) : (
            <Button variant="primary" busy={busy} disabled={!scan || selected.size === 0} onClick={doSummary}>Build summary from {selected.size} file(s)</Button>
          )}
        </>
      }>
      <div className="flex flex-col gap-3 text-[13px]">
        <Notice>
          <ShieldCheck className="mr-1 inline size-3.5" aria-hidden />
          Read-only. Prompt Studio lists files in the directory you enter and reads only the files you select. It does not follow symlinks, run scripts,
          install anything, or modify files. Secrets (.env, keys, certificates), dependency/build folders, binaries and large files are excluded; likely
          secrets in selected files are redacted. Nothing is sent anywhere.
        </Notice>
        <div className="grid gap-2 md:grid-cols-[1fr_200px_120px_auto] md:items-end">
          <Field label="Absolute directory path">{(id) => <Input id={id} placeholder="/Users/you/code/my-project" value={path} onChange={(e) => setPath(e.target.value)} />}</Field>
          <Field label="Extra exclude globs">{(id) => <Input id={id} placeholder="docs/*, *.sql" value={excludes} onChange={(e) => setExcludes(e.target.value)} />}</Field>
          <Field label="Max file KB">{(id) => <Input id={id} type="number" min={1} max={1000} value={maxKb} onChange={(e) => setMaxKb(Number(e.target.value))} />}</Field>
          <Button icon={<FolderSearch className="size-4" />} busy={busy && !scan} disabled={!path.trim()} onClick={doScan}>Scan</Button>
        </div>
        {err && <p role="alert" className="text-xs text-danger">{err}</p>}
        {scan && !summary && (
          <>
            <p className="text-xs text-muted">
              <code>{scan.root}</code> · {included.length} eligible file(s), {excluded.length} excluded{scan.truncated && " · listing truncated"} · stack: {scan.stack.join(", ") || "not detected"}
            </p>
            <div className="max-h-72 overflow-y-auto rounded-md border border-border">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-panel-2 text-left text-muted">
                  <tr><th className="w-8 px-2 py-1"><span className="sr-only">Select</span></th><th className="py-1">File</th><th className="px-2 py-1 text-right">Size</th></tr>
                </thead>
                <tbody>
                  {included.map((e) => (
                    <tr key={e.path} className="border-t border-border/60">
                      <td className="px-2 py-0.5"><input type="checkbox" aria-label={`Include ${e.path}`} checked={selected.has(e.path)} onChange={() => toggle(e.path)} /></td>
                      <td className="py-0.5 font-mono">{e.path}</td>
                      <td className="px-2 py-0.5 text-right text-muted">{formatBytes(e.size)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted">{selected.size}/{MAX_SELECTED} selected. Suggested files (manifests, configs, READMEs, entry points) are pre-selected.</p>
            <button type="button" className="self-start text-xs text-accent hover:underline" aria-expanded={showExcluded} onClick={() => setShowExcluded(!showExcluded)}>
              {showExcluded ? "Hide" : "Show"} excluded entries ({excluded.length})
            </button>
            {showExcluded && (
              <ul className="max-h-48 overflow-y-auto rounded-md border border-border px-3 py-2 font-mono text-xs">
                {excluded.map((e) => <li key={e.path}>{e.path} <span className="font-sans text-muted">— {e.reason}</span></li>)}
              </ul>
            )}
          </>
        )}
        {summary && (
          <>
            <div className="flex flex-wrap gap-1.5 text-xs">
              <Badge tone="ok">{summary.files_included.length} file(s) included</Badge>
              <Badge>{formatBytes(summary.total_bytes)}</Badge>
              {summary.redactions > 0 && <Badge tone="warn">{summary.redactions} line(s) redacted</Badge>}
              {Object.keys(summary.files_skipped).length > 0 && <Badge tone="danger">{Object.keys(summary.files_skipped).length} skipped</Badge>}
              <Button size="sm" variant="ghost" onClick={() => setSummary(null)}>Back to file selection</Button>
            </div>
            {Object.entries(summary.files_skipped).map(([f, why]) => <p key={f} className="text-xs text-danger">{f}: {why}</p>)}
            <div className="max-h-[45vh] overflow-y-auto rounded-md border border-border p-3"><Markdown content={summary.markdown} /></div>
          </>
        )}
      </div>
    </Dialog>
  );
}
