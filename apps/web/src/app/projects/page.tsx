"use client";

import { Archive, ArchiveRestore, Copy, Download, FolderPlus, Search, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useApp } from "@/components/AppContext";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { type NewProjectValues, ProjectForm } from "@/components/ProjectForm";
import { useToast } from "@/components/Toast";
import { Badge, Button, Card, Dialog, EmptyState, ErrorBanner, IconButton, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, errorMessage, qs } from "@/lib/api";
import { downloadText, readFileText } from "@/lib/download";
import { categoryLabel, relativeTime, slugify } from "@/lib/format";
import { useDebounced, useResource } from "@/lib/hooks";
import type { Page, Project, ProjectSummary } from "@/lib/types";

const MAX_IMPORT = 10 * 1024 * 1024;

export default function ProjectsPage() {
  const router = useRouter();
  const toast = useToast();
  const { settings } = useApp();
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [archived, setArchived] = useState<"false" | "true" | "all">("false");
  const dq = useDebounced(q, 250);
  const list = useResource<Page<ProjectSummary>>(`/api/projects${qs({ q: dq, tag, archived, limit: 200 })}`);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<ProjectSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const allTags = Array.from(new Set((list.data?.items ?? []).flatMap((p) => p.tags.map((t) => t.name)))).sort();

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

  async function act(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn();
      toast(ok);
      await list.reload();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  async function exportBundle(p: ProjectSummary) {
    try {
      const bundle = await api.get<unknown>(`/api/projects/${p.id}/bundle`);
      downloadText(`${slugify(p.name)}.prompt-studio.json`, JSON.stringify(bundle, null, 2), "application/json");
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  async function importFile(file: File) {
    try {
      const text = await readFileText(file, MAX_IMPORT);
      let data: unknown;
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error("The file is not valid JSON.");
      }
      const p = await api.post<Project>("/api/projects/import", data);
      toast(`Imported "${p.name}"`);
      router.push(`/projects/${p.id}`);
    } catch (e) {
      toast(`Import failed: ${errorMessage(e)}`, "error");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <PageHeader
        title="Projects"
        description="Each project holds an idea, its structured requirements, analysis, and prompt versions."
        actions={
          <>
            <input ref={fileRef} type="file" accept="application/json,.json" className="hidden" aria-label="Import project bundle file" onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])} />
            <Button icon={<Upload className="size-4" />} onClick={() => fileRef.current?.click()}>
              Import
            </Button>
            <Button variant="primary" icon={<FolderPlus className="size-4" />} onClick={() => setCreating(true)}>
              New project
            </Button>
          </>
        }
      />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-60 flex-1">
          <Search className="pointer-events-none absolute top-2.5 left-2.5 size-3.5 text-muted" aria-hidden />
          <Input aria-label="Search projects" placeholder="Search name, description or idea…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-8" />
        </div>
        <Select aria-label="Filter by tag" value={tag} onChange={(e) => setTag(e.target.value)} className="w-40">
          <option value="">All tags</option>
          {allTags.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
        <Select aria-label="Archive filter" value={archived} onChange={(e) => setArchived(e.target.value as typeof archived)} className="w-36">
          <option value="false">Active</option>
          <option value="true">Archived</option>
          <option value="all">All</option>
        </Select>
      </div>
      {list.error && <ErrorBanner message={list.error} onRetry={list.reload} />}
      <Card>
        {!list.data && list.loading ? (
          <div className="p-6"><Spinner /></div>
        ) : list.data?.items.length === 0 ? (
          <EmptyState icon={<FolderPlus className="size-6" />} title={q || tag || archived !== "false" ? "No matching projects" : "No projects yet"} action={!q && !tag && archived === "false" ? <Button variant="primary" onClick={() => setCreating(true)}>New project</Button> : undefined}>
            {q || tag ? "Try a different search or filter." : "Create a project or import a previously exported bundle."}
          </EmptyState>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="hidden px-2 py-2 font-medium md:table-cell">Category</th>
                <th className="hidden px-2 py-2 font-medium lg:table-cell">Review</th>
                <th className="px-2 py-2 font-medium">Updated</th>
                <th className="px-4 py-2 text-right font-medium"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {list.data?.items.map((p) => (
                <tr key={p.id} className="hover:bg-panel-2/60">
                  <td className="max-w-0 px-4 py-2.5">
                    <Link href={`/projects/${p.id}`} className="font-medium hover:text-accent">
                      {p.name}
                    </Link>
                    {p.archived && <Badge className="ml-2">Archived</Badge>}
                    <div className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted">
                      {p.tags.map((t) => (
                        <Badge key={t.id}>{t.name}</Badge>
                      ))}
                      <span className="truncate">{p.description}</span>
                    </div>
                  </td>
                  <td className="hidden px-2 py-2.5 text-xs text-muted md:table-cell">{categoryLabel(p.task_category)}</td>
                  <td className="hidden px-2 py-2.5 text-xs text-muted lg:table-cell">
                    {p.open_findings} open findings · {p.proposed_recommendations} proposed
                  </td>
                  <td className="px-2 py-2.5 text-xs whitespace-nowrap text-muted">{relativeTime(p.updated_at)}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-0.5">
                      <IconButton label={`Duplicate ${p.name}`} onClick={() => act(() => api.post(`/api/projects/${p.id}/duplicate`), "Project duplicated")}>
                        <Copy className="size-3.5" />
                      </IconButton>
                      <IconButton label={`Export ${p.name}`} onClick={() => exportBundle(p)}>
                        <Download className="size-3.5" />
                      </IconButton>
                      {p.archived ? (
                        <IconButton label={`Restore ${p.name}`} onClick={() => act(() => api.post(`/api/projects/${p.id}/restore`), "Project restored")}>
                          <ArchiveRestore className="size-3.5" />
                        </IconButton>
                      ) : (
                        <IconButton label={`Archive ${p.name}`} onClick={() => act(() => api.post(`/api/projects/${p.id}/archive`), "Project archived")}>
                          <Archive className="size-3.5" />
                        </IconButton>
                      )}
                      <IconButton label={`Delete ${p.name}`} onClick={() => setToDelete(p)} className="hover:text-danger">
                        <Trash2 className="size-3.5" />
                      </IconButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {list.data && list.data.total > list.data.items.length && (
        <p className="mt-2 text-xs text-muted">Showing {list.data.items.length} of {list.data.total}. Refine your search to narrow results.</p>
      )}
      <Dialog open={creating} onClose={() => setCreating(false)} title="New project">
        <ProjectForm onSubmit={create} onCancel={() => setCreating(false)} busy={busy} serverError={err} defaultAgent={settings?.default_target_agent} />
      </Dialog>
      <ConfirmDialog
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        title="Delete project"
        confirmLabel="Delete permanently"
        phrase={toDelete?.name}
        message={
          <p>
            This permanently deletes <strong>{toDelete?.name}</strong> with its requirements, analysis, recommendations and prompt
            versions. Consider exporting or archiving it instead. A database backup (Settings → Backups) can recover it.
          </p>
        }
        onConfirm={() => {
          const p = toDelete;
          setToDelete(null);
          if (p) void act(() => api.del(`/api/projects/${p.id}?confirm=true`), "Project deleted");
        }}
      />
    </div>
  );
}
