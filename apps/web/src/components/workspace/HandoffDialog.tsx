"use client";

import { Copy, FolderOutput } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { copyText } from "@/lib/download";
import { formatBytes, PROFILE_LABELS } from "@/lib/format";
import { Markdown } from "../Markdown";
import { useToast } from "../Toast";
import { Badge, Button, Dialog, Field, Input, Notice, Select } from "../ui";

interface PlanFile {
  path: string;
  purpose: string;
  exists: boolean;
  existing_size: number | null;
  content: string;
}
interface Plan {
  root: string;
  profile_id: string;
  files: PlanFile[];
  command: string;
  command_note: string;
}
interface WriteResult {
  root: string;
  written: string[];
  skipped_existing: string[];
  backups: string[];
  command: string;
  command_note: string;
}

const CODING_PROFILES = ["claude_code", "codex", "cursor", "generic_coding"];

/** Explicit, previewed handoff of instruction files + prompt into a local project. Never executes anything. */
export function HandoffDialog({
  open,
  onClose,
  projectId,
  defaultProfile,
  source,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  defaultProfile: string;
  source: { version_id: string } | { content: string };
}) {
  const toast = useToast();
  const [path, setPath] = useState("");
  const [profile, setProfile] = useState(CODING_PROFILES.includes(defaultProfile) ? defaultProfile : "claude_code");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [overwrite, setOverwrite] = useState<Set<string>>(new Set());
  const [authorized, setAuthorized] = useState(false);
  const [result, setResult] = useState<WriteResult | null>(null);
  const [view, setView] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const reset = () => {
    setPlan(null);
    setResult(null);
    setOverwrite(new Set());
    setAuthorized(false);
    setErr(null);
  };

  async function preview() {
    setBusy(true);
    reset();
    try {
      setPlan(await api.post<Plan>(`/api/projects/${projectId}/handoff/preview`, { path: path.trim(), profile_id: profile, ...source }));
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function write() {
    setBusy(true);
    setErr(null);
    try {
      setResult(await api.post<WriteResult>(`/api/projects/${projectId}/handoff/write`, {
        path: path.trim(), profile_id: profile, ...source, overwrite: Array.from(overwrite), confirm: "WRITE",
      }));
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const toWrite = plan?.files.filter((f) => !f.exists || overwrite.has(f.path)) ?? [];
  return (
    <Dialog open={open} onClose={() => { reset(); onClose(); }} title="Hand off to a coding agent" wide
      footer={
        <>
          <Button onClick={() => { reset(); onClose(); }}>{result ? "Close" : "Cancel"}</Button>
          {plan && !result && (
            <Button variant="primary" busy={busy} disabled={!authorized || toWrite.length === 0} onClick={write}>
              Write {toWrite.length} file(s)
            </Button>
          )}
        </>
      }>
      <div className="flex flex-col gap-3 text-[13px]">
        <Notice>
          Prompt Studio writes the agent’s instruction file and the prompt into a folder you choose, after you review them. Existing files are kept unless
          you tick “overwrite” (a backup is made first). It <strong>never runs the agent or any command</strong> — you copy the command yourself.
        </Notice>
        <div className="grid gap-2 md:grid-cols-[1fr_220px_auto] md:items-end">
          <Field label="Project directory (absolute path)">{(id) => <Input id={id} value={path} placeholder="/Users/you/code/my-project" onChange={(e) => { setPath(e.target.value); reset(); }} />}</Field>
          <Field label="Agent">{(id) => (
            <Select id={id} value={profile} onChange={(e) => { setProfile(e.target.value); reset(); }}>
              {CODING_PROFILES.map((p) => <option key={p} value={p}>{PROFILE_LABELS[p]}</option>)}
            </Select>)}
          </Field>
          <Button icon={<FolderOutput className="size-4" />} busy={busy && !plan} disabled={!path.trim()} onClick={preview}>Preview</Button>
        </div>
        {err && <p role="alert" className="text-xs text-danger">{err}</p>}

        {plan && !result && (
          <>
            <p className="text-xs text-muted">Files for <code>{plan.root}</code>:</p>
            <ul className="flex flex-col gap-1.5">
              {plan.files.map((f) => (
                <li key={f.path} className="rounded-md border border-border px-3 py-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-medium">{f.path}</code>
                    {f.exists ? <Badge tone="warn">exists ({formatBytes(f.existing_size)})</Badge> : <Badge tone="ok">new</Badge>}
                    <span className="text-muted">{f.purpose}</span>
                    <span className="ml-auto flex items-center gap-2">
                      {f.exists && (
                        <label className="flex items-center gap-1">
                          <input type="checkbox" checked={overwrite.has(f.path)} onChange={(e) => setOverwrite((s) => { const n = new Set(s); if (e.target.checked) n.add(f.path); else n.delete(f.path); return n; })} />
                          overwrite (backup first)
                        </label>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => setView(view === f.path ? null : f.path)}>{view === f.path ? "Hide" : "View"}</Button>
                    </span>
                  </div>
                  {view === f.path && <div className="mt-2 max-h-64 overflow-y-auto rounded border border-border p-2"><Markdown content={f.content} /></div>}
                </li>
              ))}
            </ul>
            <label className="flex items-start gap-2 text-xs">
              <input type="checkbox" checked={authorized} onChange={(e) => setAuthorized(e.target.checked)} className="mt-0.5" />
              <span>I authorize Prompt Studio to write {toWrite.length} file(s) into <code>{plan.root}</code>.</span>
            </label>
          </>
        )}

        {result && (
          <div className="flex flex-col gap-2 text-xs">
            <p className="text-ok">Wrote {result.written.length} file(s): {result.written.join(", ") || "none"}.</p>
            {result.skipped_existing.length > 0 && <p className="text-muted">Kept existing: {result.skipped_existing.join(", ")}</p>}
            {result.backups.length > 0 && <p className="text-muted">Backups: {result.backups.join(", ")}</p>}
            <p className="font-medium">Next step (run it yourself):</p>
            <div className="flex items-start gap-2">
              <pre className="flex-1 overflow-x-auto rounded-md border border-border bg-panel-2 p-2 font-mono">{result.command}</pre>
              <Button size="sm" icon={<Copy className="size-3" />} onClick={async () => toast((await copyText(result.command)) ? "Command copied" : "Copy failed", "info")}>Copy</Button>
            </div>
            <p className="text-muted">{result.command_note} Command syntax may change between agent versions; check your agent’s documentation.</p>
          </div>
        )}
      </div>
    </Dialog>
  );
}
