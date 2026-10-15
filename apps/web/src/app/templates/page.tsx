"use client";

import { Copy, ExternalLink, FileStack, Pencil, Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { emptyTemplate, fromTemplate, type TemplateDraft, TemplateEditor } from "@/components/TemplateEditor";
import { useToast } from "@/components/Toast";
import { Badge, Button, Card, CardHeader, Dialog, EmptyState, ErrorBanner, Field, IconButton, Input, PageHeader, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { categoryLabel, REQ_KIND_LABELS } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import type { AgentProfile, Project, TaskTemplate } from "@/lib/types";

export default function TemplatesPage() {
  const router = useRouter();
  const templates = useResource<TaskTemplate[]>("/api/templates");
  const profiles = useResource<AgentProfile[]>("/api/profiles");
  const [chosen, setChosen] = useState<TaskTemplate | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const toast = useToast();
  const [editing, setEditing] = useState<{ id: string | null; draft: TemplateDraft } | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [editErr, setEditErr] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<TaskTemplate | null>(null);

  async function saveTemplate(d: TemplateDraft) {
    if (!editing) return;
    setEditBusy(true);
    setEditErr(null);
    try {
      if (editing.id) await api.put(`/api/templates/${editing.id}`, d);
      else await api.post("/api/templates", d);
      toast("Template saved");
      setEditing(null);
      await templates.reload();
    } catch (e) {
      setEditErr(errorMessage(e));
    } finally {
      setEditBusy(false);
    }
  }

  const card = (t: TaskTemplate) => (
    <Card key={t.id} className="flex flex-col p-3">
      <div className="mb-1 flex items-center gap-2">
        <FileStack className="size-4 shrink-0 text-accent" aria-hidden />
        <h3 className="flex-1 truncate text-[13px] font-semibold">{t.name}</h3>
        {t.builtin ? (
          <IconButton label={`Duplicate ${t.name} as custom template`} onClick={() => setEditing({ id: null, draft: { ...fromTemplate(t), name: `${t.name} (custom)` } })}><Copy className="size-3.5" /></IconButton>
        ) : (
          <>
            <IconButton label={`Edit ${t.name}`} onClick={() => setEditing({ id: t.id, draft: fromTemplate(t) })}><Pencil className="size-3.5" /></IconButton>
            <IconButton label={`Delete ${t.name}`} className="hover:text-danger" onClick={() => setToDelete(t)}><Trash2 className="size-3.5" /></IconButton>
          </>
        )}
      </div>
      <p className="text-xs text-muted">{t.description || "No description"}</p>
      <div className="mt-2 flex flex-wrap gap-1"><Badge>{categoryLabel(t.category)}</Badge>{t.requirements.length > 0 && <Badge>{t.requirements.length} proposed requirement(s)</Badge>}</div>
      <Button size="sm" className="mt-3 self-start" onClick={() => { setChosen(t); setName(t.name); }}>Use template</Button>
    </Card>
  );

  async function create() {
    if (!chosen || !name.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const p = await api.post<Project>("/api/projects/from-template", { template_id: chosen.id, name: name.trim() });
      router.push(`/projects/${p.id}`);
    } catch (e) {
      setErr(errorMessage(e));
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <PageHeader title="Templates" description="Task templates pre-fill a project. Template requirements start as “proposed” so nothing enters your spec without review." />
      {templates.error && <ErrorBanner message={templates.error} onRetry={templates.reload} />}
      {!templates.data ? <Spinner /> : (
        <>
          <h2 className="mb-2 text-base font-semibold">Built-in</h2>
          <div className="mb-6 grid gap-3 md:grid-cols-2 lg:grid-cols-4">{templates.data.filter((t) => t.builtin).map(card)}</div>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-base font-semibold">Your templates</h2>
            <Button size="sm" variant="primary" icon={<Plus className="size-3.5" />} onClick={() => setEditing({ id: null, draft: emptyTemplate() })}>New template</Button>
          </div>
          {templates.data.some((t) => !t.builtin) ? (
            <div className="mb-8 grid gap-3 md:grid-cols-2 lg:grid-cols-4">{templates.data.filter((t) => !t.builtin).map(card)}</div>
          ) : (
            <Card className="mb-8"><EmptyState title="No custom templates yet">Create one here, duplicate a built-in template, or use “Save as template” in a project workspace.</EmptyState></Card>
          )}
        </>
      )}

      <h2 className="mb-1 text-base font-semibold">Agent export profiles</h2>
      <p className="mb-3 text-[13px] text-muted">Versioned conventions used for prompt structure and instruction-file exports. Verified against official documentation on the date shown; conventions may have changed since.</p>
      {!profiles.data ? <Spinner /> : (
        <div className="grid gap-3 lg:grid-cols-2">
          {profiles.data.map((p) => (
            <Card key={p.id}>
              <CardHeader title={`${p.name} · v${p.version}`} subtitle={`Verified ${p.verified_on}`}
                actions={p.docs_url ? <a href={p.docs_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-accent hover:underline">Docs <ExternalLink className="size-3" /></a> : undefined} />
              <dl className="grid grid-cols-[150px_1fr] gap-x-3 gap-y-1.5 px-4 py-3 text-xs">
                <dt className="text-muted">Output formats</dt><dd>{p.output_formats.join(", ")}</dd>
                <dt className="text-muted">Instruction structure</dt><dd>{p.instruction_structure.join(" → ")}</dd>
                <dt className="text-muted">Context requirements</dt><dd>{p.context_requirements.join("; ")}</dd>
                <dt className="text-muted">Instruction files</dt>
                <dd>{p.instruction_files.length ? p.instruction_files.map((f) => <div key={f.path}><code>{f.path}</code> — {f.purpose}</div>) : "None"}</dd>
                <dt className="text-muted">Known limitations</dt><dd>{p.limitations.join("; ") || "—"}</dd>
                <dt className="text-muted">Unsupported</dt><dd>{p.unsupported.join("; ") || "—"}</dd>
              </dl>
            </Card>
          ))}
        </div>
      )}

      {editing && (
        <TemplateEditor open title={editing.id ? "Edit template" : "New template"} initial={editing.draft} busy={editBusy} error={editErr}
          onClose={() => { setEditing(null); setEditErr(null); }} onSave={saveTemplate} />
      )}
      <ConfirmDialog open={toDelete !== null} onClose={() => setToDelete(null)} title="Delete template" confirmLabel="Delete template"
        message={<p>Delete the template <strong>{toDelete?.name}</strong>? Projects created from it are not affected.</p>}
        onConfirm={async () => {
          const t = toDelete;
          setToDelete(null);
          if (!t) return;
          try { await api.del(`/api/templates/${t.id}?confirm=true`); toast("Template deleted"); await templates.reload(); } catch (e) { toast(errorMessage(e), "error"); }
        }} />
      <Dialog open={chosen !== null} onClose={() => setChosen(null)} title={`New project from “${chosen?.name ?? ""}”`}
        footer={<><Button onClick={() => setChosen(null)}>Cancel</Button><Button variant="primary" busy={busy} disabled={!name.trim()} onClick={create}>Create project</Button></>}>
        <div className="flex flex-col gap-3 text-xs">
          <Field label="Project name" error={err}>{(id) => <Input id={id} value={name} maxLength={200} onChange={(e) => setName(e.target.value)} autoFocus />}</Field>
          <div>
            <p className="mb-1 font-medium">Idea skeleton</p>
            <pre className="rounded border border-border bg-panel-2 p-2 font-mono whitespace-pre-wrap">{chosen?.idea}</pre>
          </div>
          {chosen && chosen.requirements.length > 0 && (
            <div>
              <p className="mb-1 font-medium">Proposed requirements (you will review them)</p>
              <ul className="list-disc pl-4">{chosen.requirements.map((r, i) => <li key={i}><span className="text-muted">{REQ_KIND_LABELS[r.kind]}:</span> {r.text}</li>)}</ul>
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}
