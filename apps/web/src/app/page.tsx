"use client";

import { AlertTriangle, ArrowRight, FileText, FolderPlus, Layers } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useApp } from "@/components/AppContext";
import { type NewProjectValues, ProjectForm } from "@/components/ProjectForm";
import { Button, Card, CardHeader, Dialog, EmptyState, EngineBadge, ErrorBanner, PageHeader, SeverityBadge, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { relativeTime, runtimeLabel } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import type { Dashboard, Project } from "@/lib/types";

export default function DashboardPage() {
  const dash = useResource<Dashboard>("/api/dashboard");
  const { models, aiReady, aiUnavailableReason, settings } = useApp();
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create(v: NewProjectValues) {
    setBusy(true);
    setErr(null);
    try {
      const p = await api.post<Project>("/api/projects", {
        name: v.name,
        description: v.description,
        original_idea: v.original_idea,
        config: { task_category: v.task_category, target_agent: v.target_agent },
      });
      router.push(`/projects/${p.id}`);
    } catch (e) {
      setErr(errorMessage(e));
      setBusy(false);
    }
  }

  const d = dash.data;
  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <PageHeader
        title="Dashboard"
        description="Your local prompt workbench. Everything here is stored on this machine."
        actions={
          <>
            <Button icon={<Layers className="size-4" />} onClick={() => router.push("/templates")}>
              From template
            </Button>
            <Button variant="primary" icon={<FolderPlus className="size-4" />} onClick={() => setCreating(true)}>
              New project
            </Button>
          </>
        }
      />
      {dash.error && <ErrorBanner message={dash.error} onRetry={dash.reload} />}
      {!d && dash.loading && <Spinner />}
      {d && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="Recent projects" actions={<Link className="text-xs text-accent hover:underline" href="/projects">All projects</Link>} />
            {d.recent_projects.length === 0 ? (
              <EmptyState icon={<FolderPlus className="size-6" />} title="No projects yet" action={<Button variant="primary" onClick={() => setCreating(true)}>Create your first project</Button>}>
                A project turns a rough idea into a structured specification and optimized prompts.
              </EmptyState>
            ) : (
              <ul className="divide-y divide-border">
                {d.recent_projects.map((p) => (
                  <li key={p.id}>
                    <Link href={`/projects/${p.id}`} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-panel-2">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-medium">{p.name}</p>
                        <p className="truncate text-xs text-muted">{p.description || "No description"}</p>
                      </div>
                      <span className="shrink-0 text-xs text-muted">{relativeTime(p.updated_at)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader title="Local AI runtime" />
            <div className="flex flex-col gap-2 px-4 py-3 text-[13px]">
              <Row label="Runtime">{models ? runtimeLabel(models.provider) : "—"}</Row>
              <Row label="Status">{models ? (models.available ? `Connected${models.version ? ` (v${models.version})` : ""}` : "Not reachable") : "Checking…"}</Row>
              <Row label="Endpoint"><code className="text-xs">{models?.endpoint ?? settings?.ollama_url ?? "—"}</code></Row>
              <Row label="Selected model">{models?.selected_model ?? "None"}</Row>
              <Row label="Operating mode">{aiReady ? "Local AI available on request" : "Rule-based (offline)"}</Row>
              {!aiReady && <p className="text-xs text-muted">{aiUnavailableReason}</p>}
              <Link href="/models" className="mt-1 inline-flex items-center gap-1 text-xs text-accent hover:underline">
                Manage local models <ArrowRight className="size-3" />
              </Link>
            </div>
          </Card>

          <Card>
            <CardHeader title="Library" />
            <div className="grid grid-cols-2 gap-3 px-4 py-3">
              <Stat label="Active projects" value={d.counts.projects} />
              <Stat label="Archived projects" value={d.counts.archived_projects} />
              <Stat label="Saved prompts" value={d.counts.prompts} />
              <Stat label="Prompt versions" value={d.counts.versions} />
            </div>
          </Card>

          <Card>
            <CardHeader title="Drafts requiring review" subtitle="Projects with proposed recommendations" />
            {d.needs_review.length === 0 ? (
              <p className="px-4 py-4 text-xs text-muted">Nothing awaiting review.</p>
            ) : (
              <ul className="divide-y divide-border">
                {d.needs_review.map((r) => (
                  <li key={r.project_id}>
                    <Link href={`/projects/${r.project_id}?panel=recommendations`} className="flex items-center justify-between px-4 py-2 text-[13px] hover:bg-panel-2">
                      <span className="truncate">{r.project_name}</span>
                      <span className="text-xs text-muted">{r.proposed_recommendations} proposed</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader title="Recent prompt versions" />
            {d.recent_versions.length === 0 ? (
              <p className="px-4 py-4 text-xs text-muted">No saved prompt versions yet.</p>
            ) : (
              <ul className="divide-y divide-border">
                {d.recent_versions.map((v) => (
                  <li key={v.id}>
                    <Link href={`/library/${v.prompt_id}`} className="flex items-center gap-2 px-4 py-2 text-[13px] hover:bg-panel-2">
                      <FileText className="size-3.5 shrink-0 text-muted" aria-hidden />
                      <span className="flex-1 truncate">{v.prompt_title} <span className="text-muted">v{v.number}</span></span>
                      <EngineBadge engine={v.generator} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="lg:col-span-3">
            <CardHeader title="Recent analysis findings" subtitle="Open findings of medium severity or higher" />
            {d.recent_findings.length === 0 ? (
              <p className="px-4 py-4 text-xs text-muted">No open findings. Run an analysis from a project workspace.</p>
            ) : (
              <ul className="divide-y divide-border">
                {d.recent_findings.map((f) => (
                  <li key={f.id}>
                    <Link href={`/projects/${f.project_id}?panel=findings`} className="flex items-center gap-2 px-4 py-2 text-[13px] hover:bg-panel-2">
                      <AlertTriangle className="size-3.5 shrink-0 text-muted" aria-hidden />
                      <SeverityBadge severity={f.severity} />
                      <span className="flex-1 truncate">{f.title}</span>
                      <span className="hidden truncate text-xs text-muted sm:inline">{f.project_name}</span>
                      <EngineBadge engine={f.engine} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
      <Dialog open={creating} onClose={() => setCreating(false)} title="New project">
        <ProjectForm onSubmit={create} onCancel={() => setCreating(false)} busy={busy} serverError={err} defaultAgent={settings?.default_target_agent} />
      </Dialog>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs text-muted">{label}</span>
      <span className="truncate text-right">{children}</span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      <p className="text-xs text-muted">{label}</p>
    </div>
  );
}
