"use client";

import { ExternalLink, FileStack } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, Dialog, ErrorBanner, Field, Input, PageHeader, Spinner } from "@/components/ui";
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
        <div className="mb-8 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {templates.data.map((t) => (
            <Card key={t.id} className="flex flex-col p-3">
              <div className="mb-1 flex items-center gap-2">
                <FileStack className="size-4 text-accent" aria-hidden />
                <h2 className="text-[13px] font-semibold">{t.name}</h2>
              </div>
              <p className="text-xs text-muted">{t.description}</p>
              <div className="mt-2 flex flex-wrap gap-1"><Badge>{categoryLabel(t.category)}</Badge>{t.requirements.length > 0 && <Badge>{t.requirements.length} proposed requirement(s)</Badge>}</div>
              <Button size="sm" className="mt-3 self-start" onClick={() => { setChosen(t); setName(t.name); }}>Use template</Button>
            </Card>
          ))}
        </div>
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
