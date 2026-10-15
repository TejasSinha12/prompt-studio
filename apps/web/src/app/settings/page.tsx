"use client";

import { Archive, DatabaseBackup, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useApp } from "@/components/AppContext";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorBanner, Field, Input, Notice, PageHeader, Select, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatBytes, formatDate, PROFILE_LABELS } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import type { AppSettings, Backup, BackupValidation, SystemInfo } from "@/lib/types";

export default function SettingsPage() {
  const toast = useToast();
  const { refresh } = useApp();
  const saved = useResource<AppSettings>("/api/settings");
  const sys = useResource<SystemInfo>("/api/system");
  const backups = useResource<Backup[]>("/api/backups");
  const [form, setForm] = useState<AppSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [validation, setValidation] = useState<Record<string, BackupValidation>>({});
  const [restore, setRestore] = useState<Backup | null>(null);
  const [removing, setRemoving] = useState<Backup | null>(null);
  const [wipe, setWipe] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (saved.data) setForm(saved.data);
  }, [saved.data]);
  const dirty = form && saved.data && JSON.stringify(form) !== JSON.stringify(saved.data);

  async function save() {
    if (!form) return;
    setSaving(true);
    setErr(null);
    try {
      const s = await api.put<AppSettings>("/api/settings", form);
      saved.setData(s);
      toast("Settings saved");
      await refresh();
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  const num = (k: keyof AppSettings) => (e: React.ChangeEvent<HTMLInputElement>) => form && setForm({ ...form, [k]: Number(e.target.value) });

  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      <PageHeader title="Settings" description="Application settings are stored separately from project content and never included in exports." />
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader title="Local AI (Ollama)" />
          {!form ? <div className="p-4"><Spinner /></div> : (
            <div className="grid gap-3 px-4 py-3 md:grid-cols-2">
              <Field label="Ollama endpoint" hint="Must be a loopback address unless remote is explicitly allowed" className="md:col-span-2">
                {(id) => <Input id={id} value={form.ollama_url} onChange={(e) => setForm({ ...form, ollama_url: e.target.value })} />}
              </Field>
              <label className="flex items-start gap-2 text-xs md:col-span-2">
                <input type="checkbox" checked={form.allow_remote_ollama} onChange={(e) => setForm({ ...form, allow_remote_ollama: e.target.checked })} className="mt-0.5" />
                <span>Allow a non-loopback endpoint. <strong className="text-warn">Prompt content, requirements and project text you send to local-AI actions would then leave this machine.</strong> Off by default.</span>
              </label>
              <Field label="Request timeout (seconds)" hint="5–1800">{(id) => <Input id={id} type="number" min={5} max={1800} value={form.timeout_seconds} onChange={num("timeout_seconds")} />}</Field>
              <Field label="Retries for transient failures" hint="0–5; timeouts are not retried">{(id) => <Input id={id} type="number" min={0} max={5} value={form.max_retries} onChange={num("max_retries")} />}</Field>
              <Field label="Context size (num_ctx)" hint="Larger uses more memory">{(id) => <Input id={id} type="number" min={512} max={262144} step={512} value={form.num_ctx} onChange={num("num_ctx")} />}</Field>
              <Field label="Temperature" hint="0–2; lower is more deterministic">{(id) => <Input id={id} type="number" min={0} max={2} step={0.1} value={form.temperature} onChange={num("temperature")} />}</Field>
              <Field label="Concurrent local-AI jobs" hint="1–4; 1 is recommended on laptops">{(id) => <Input id={id} type="number" min={1} max={4} value={form.max_concurrent_jobs} onChange={num("max_concurrent_jobs")} />}</Field>
              <Field label="Default target agent">
                {(id) => (
                  <Select id={id} value={form.default_target_agent} onChange={(e) => setForm({ ...form, default_target_agent: e.target.value as AppSettings["default_target_agent"] })}>
                    {Object.entries(PROFILE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </Select>
                )}
              </Field>
              {err && <p role="alert" className="text-xs text-danger md:col-span-2">{err}</p>}
              <div className="flex justify-end gap-2 md:col-span-2">
                <Button disabled={!dirty} onClick={() => saved.data && setForm(saved.data)}>Reset</Button>
                <Button variant="primary" busy={saving} disabled={!dirty} onClick={save}>Save settings</Button>
              </div>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Data & privacy" />
          <div className="flex flex-col gap-2 px-4 py-3 text-[13px]">
            {sys.data ? (
              <dl className="grid grid-cols-[140px_1fr] gap-x-3 gap-y-1 text-xs">
                <dt className="text-muted">Data directory</dt><dd><code>{sys.data.data_dir}</code></dd>
                <dt className="text-muted">Database</dt><dd><code>{sys.data.database}</code></dd>
                <dt className="text-muted">Backups</dt><dd><code>{sys.data.backups_dir}</code></dd>
                <dt className="text-muted">API token</dt><dd>{sys.data.api_token_enabled ? "Enabled" : "Not set (see docs to enable)"}</dd>
                <dt className="text-muted">Version</dt><dd>{sys.data.version}</dd>
              </dl>
            ) : <Spinner />}
            <Notice><ShieldCheck className="mr-1 inline size-3.5" aria-hidden />No telemetry. No cloud providers. The UI is restricted by Content-Security-Policy to its own origin. Data is not encrypted at rest — use full-disk encryption.</Notice>
          </div>
        </Card>

        <Card>
          <CardHeader title="Backups" subtitle="Consistent SQLite snapshots stored in the backups directory"
            actions={<Button size="sm" icon={<DatabaseBackup className="size-3.5" />} busy={busy} onClick={async () => {
              setBusy(true);
              try { const b = await api.post<Backup>("/api/backups"); toast(`Backup created: ${b.name}`); await backups.reload(); } catch (e) { toast(errorMessage(e), "error"); } finally { setBusy(false); }
            }}>Create backup</Button>} />
          {backups.error && <div className="p-3"><ErrorBanner message={backups.error} onRetry={backups.reload} /></div>}
          {!backups.data ? <div className="p-4"><Spinner /></div> : backups.data.length === 0 ? (
            <EmptyState icon={<Archive className="size-6" />} title="No backups yet">Create a backup before large changes. Restoring and deleting all data create safety backups automatically.</EmptyState>
          ) : (
            <ul className="divide-y divide-border">
              {backups.data.map((b) => {
                const v = validation[b.name];
                return (
                  <li key={b.name} className="px-4 py-2.5 text-[13px]">
                    <div className="flex flex-wrap items-center gap-2">
                      <code className="flex-1 truncate text-xs">{b.name}</code>
                      <span className="text-xs text-muted">{formatBytes(b.size_bytes)} · {formatDate(b.created_at)}</span>
                      {v && <Badge tone={v.valid ? "ok" : "danger"}>{v.valid ? "valid" : "invalid"}</Badge>}
                      <Button size="sm" onClick={async () => {
                        try { const r = await api.post<BackupValidation>(`/api/backups/${encodeURIComponent(b.name)}/validate`); setValidation((x) => ({ ...x, [b.name]: r })); } catch (e) { toast(errorMessage(e), "error"); }
                      }}>Validate</Button>
                      <Button size="sm" icon={<RotateCcw className="size-3" />} onClick={() => setRestore(b)}>Restore</Button>
                      <Button size="sm" variant="danger" icon={<Trash2 className="size-3" />} onClick={() => setRemoving(b)}>Delete</Button>
                    </div>
                    {v && (
                      <ul className="mt-1.5 grid gap-0.5 text-xs md:grid-cols-2">
                        {v.checks.map((c) => <li key={c.name} className={c.ok ? "text-ok" : "text-danger"}>{c.ok ? "✓" : "✗"} {c.name}{c.detail ? ` — ${c.detail}` : ""}</li>)}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card className="border-danger/40">
          <CardHeader title="Delete all data" subtitle="Removes all projects, prompts, versions, analysis and tags. Settings and backups are kept." actions={<Button size="sm" variant="danger" onClick={() => setWipe(true)}>Delete all data…</Button>} />
          <p className="px-4 py-3 text-xs text-muted">A safety backup is created first. To remove everything including backups, stop the app and delete the data directory shown above.</p>
        </Card>
      </div>

      <ConfirmDialog open={restore !== null} onClose={() => setRestore(null)} title="Restore backup" confirmLabel="Restore" phrase="RESTORE" busy={busy}
        message={<p>Replace the current database with <code>{restore?.name}</code>? The backup is validated first and a safety backup of the current data is created automatically. Any running local-AI jobs are cancelled.</p>}
        onConfirm={async () => {
          if (!restore) return;
          setBusy(true);
          try {
            const r = await api.post<{ restored: string; safety_backup: string }>(`/api/backups/${encodeURIComponent(restore.name)}/restore`, { confirm: "RESTORE" });
            toast(`Restored. Safety backup: ${r.safety_backup}`);
            setRestore(null);
            await Promise.all([backups.reload(), saved.reload(), refresh()]);
          } catch (e) { toast(errorMessage(e), "error"); } finally { setBusy(false); }
        }} />
      <ConfirmDialog open={removing !== null} onClose={() => setRemoving(null)} title="Delete backup" confirmLabel="Delete backup"
        message={<p>Permanently delete <code>{removing?.name}</code>?</p>}
        onConfirm={async () => {
          if (!removing) return;
          try { await api.del(`/api/backups/${encodeURIComponent(removing.name)}?confirm=true`); toast("Backup deleted"); setRemoving(null); await backups.reload(); } catch (e) { toast(errorMessage(e), "error"); }
        }} />
      <ConfirmDialog open={wipe} onClose={() => setWipe(false)} title="Delete all data" confirmLabel="Delete all data" phrase="DELETE ALL DATA" busy={busy}
        message={<p>This deletes every project, requirement, recommendation, prompt, version and evaluation. A safety backup is created first.</p>}
        onConfirm={async () => {
          setBusy(true);
          try { const r = await api.post<{ safety_backup: string }>("/api/data/delete-all", { confirm: "DELETE ALL DATA" }); toast(`All data deleted. Safety backup: ${r.safety_backup}`); setWipe(false); await backups.reload(); } catch (e) { toast(errorMessage(e), "error"); } finally { setBusy(false); }
        }} />
    </div>
  );
}
