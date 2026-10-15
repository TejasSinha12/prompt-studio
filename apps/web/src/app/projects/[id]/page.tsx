"use client";

import { Archive, ArchiveRestore, Copy, Download, PanelRightClose, PanelRightOpen, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PromptVersions } from "@/components/PromptVersions";
import { useToast } from "@/components/Toast";
import { Badge, Button, EmptyState, ErrorBanner, Kbd, Spinner, Tabs } from "@/components/ui";
import { ClarifyPanel } from "@/components/workspace/ClarifyPanel";
import { FindingsPanel } from "@/components/workspace/FindingsPanel";
import { HistoryPanel } from "@/components/workspace/HistoryPanel";
import { IdeaPanel, type ProjectDraft } from "@/components/workspace/IdeaPanel";
import { PromptPanel } from "@/components/workspace/PromptPanel";
import { RecommendationsPanel } from "@/components/workspace/RecommendationsPanel";
import { RequirementsPanel } from "@/components/workspace/RequirementsPanel";
import { ApiError, api, errorMessage } from "@/lib/api";
import { downloadText } from "@/lib/download";
import { slugify } from "@/lib/format";
import { useLocalStorage, useResource } from "@/lib/hooks";
import type { AnalysisRun, Finding, Page, Project, PromptSummary, Recommendation } from "@/lib/types";

type MainTab = "idea" | "requirements" | "prompt" | "versions";
type SideTab = "findings" | "recommendations" | "clarify" | "history";

function toDraft(p: Project): ProjectDraft {
  return {
    name: p.name,
    description: p.description,
    original_idea: p.original_idea,
    tech_stack: p.tech_stack,
    tags: p.tags.map((t) => t.name).join(", "),
    config: { ...p.config },
  };
}

function parseTags(s: string): string[] {
  return Array.from(new Set(s.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean)));
}

export default function WorkspacePage() {
  return (
    <Suspense fallback={<div className="p-6"><Spinner /></div>}>
      <Workspace />
    </Suspense>
  );
}

function Workspace() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const toast = useToast();
  const project = useResource<Project>(`/api/projects/${id}`);
  const findings = useResource<Finding[]>(`/api/projects/${id}/findings`);
  const runs = useResource<AnalysisRun[]>(`/api/projects/${id}/analysis-runs`);
  const recs = useResource<Recommendation[]>(`/api/projects/${id}/recommendations`);
  const prompts = useResource<Page<PromptSummary>>(`/api/prompts?project_id=${id}&archived=all&limit=50`);

  const [draft, setDraft] = useState<ProjectDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [main, setMain] = useState<MainTab>("idea");
  const initialSide = (search.get("panel") as SideTab | null) ?? "findings";
  const [side, setSide] = useState<SideTab>(initialSide);
  const [sideOpen, setSideOpen] = useLocalStorage("ps-side-open", true);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [versionsKey, setVersionsKey] = useState(0);
  const [historyKey, setHistoryKey] = useState(0);

  const p = project.data;
  useEffect(() => {
    if (p && (draft === null || !conflict)) setDraft((d) => (d === null ? toDraft(p) : d));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p]);

  const dirty = useMemo(() => {
    if (!p || !draft) return false;
    const base = toDraft(p);
    return JSON.stringify({ ...base, tags: parseTags(base.tags) }) !== JSON.stringify({ ...draft, tags: parseTags(draft.tags) });
  }, [p, draft]);

  const reloadAll = useCallback(async () => {
    await Promise.all([project.reload(), findings.reload(), runs.reload(), recs.reload(), prompts.reload()]);
    setHistoryKey((k) => k + 1);
  }, [project, findings, runs, recs, prompts]);

  const save = useCallback(async () => {
    if (!p || !draft || !dirty || saving) return;
    if (!draft.name.trim()) {
      setSaveError("Project name is required.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await api.patch<Project>(`/api/projects/${p.id}`, {
        revision: p.revision,
        name: draft.name.trim(),
        description: draft.description,
        original_idea: draft.original_idea,
        tech_stack: draft.tech_stack,
        config: draft.config,
        tags: parseTags(draft.tags).slice(0, 20),
      });
      project.setData(updated);
      setDraft(toDraft(updated));
      setHistoryKey((k) => k + 1);
      toast("Project saved");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setConflict(true);
      else setSaveError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }, [p, draft, dirty, saving, project, toast]);

  // Ctrl/Cmd+S saves; warn before leaving with unsaved edits (tab close and in-app links).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s" && main === "idea") {
        e.preventDefault();
        void save();
      }
    };
    const onUnload = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    const onClick = (e: MouseEvent) => {
      if (!dirty) return;
      const a = (e.target as HTMLElement).closest("a[href]");
      if (a && a.getAttribute("href")?.startsWith("/") && !window.confirm("You have unsaved changes to this project. Leave without saving?")) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("beforeunload", onUnload);
    document.addEventListener("click", onClick, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("beforeunload", onUnload);
      document.removeEventListener("click", onClick, true);
    };
  }, [dirty, save, main]);

  async function simple(fn: () => Promise<unknown>, msg: string) {
    try {
      await fn();
      toast(msg);
      await reloadAll();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  if (project.error && !p)
    return (
      <div className="p-6">
        <ErrorBanner message={project.error} onRetry={project.reload} />
        <Link href="/projects" className="mt-3 inline-block text-xs text-accent hover:underline">Back to projects</Link>
      </div>
    );
  if (!p || !draft) return <div className="p-6"><Spinner /></div>;

  const openFindings = (findings.data ?? []).filter((f) => f.status === "open").length;
  const proposed = (recs.data ?? []).filter((r) => r.status === "proposed").length;
  const projectPrompt = prompts.data?.items[0];
  const specVersion = `${p.revision}:${p.updated_at}`;
  const saveState = saving ? "Saving…" : conflict ? "Conflict" : dirty ? "Unsaved changes" : "All changes saved";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-border bg-panel px-4 py-2">
        <div className="min-w-0 flex-1">
          <nav aria-label="Breadcrumb" className="text-xs text-muted">
            <Link href="/projects" className="hover:text-text">Projects</Link> /
          </nav>
          <h1 className="flex items-center gap-2 truncate text-base font-semibold">
            {p.name}
            {p.archived && <Badge>Archived</Badge>}
          </h1>
        </div>
        <span role="status" aria-live="polite" className={`text-xs ${dirty || conflict ? "text-warn" : "text-muted"}`}>{saveState}</span>
        <Button variant="primary" size="sm" icon={<Save className="size-3.5" />} busy={saving} disabled={!dirty || conflict} onClick={save} title="Save (Ctrl/Cmd+S)">
          Save
        </Button>
        <Button size="sm" icon={<Copy className="size-3.5" />} onClick={async () => {
          try { const d = await api.post<Project>(`/api/projects/${p.id}/duplicate`); toast("Duplicated"); router.push(`/projects/${d.id}`); } catch (e) { toast(errorMessage(e), "error"); }
        }}>Duplicate</Button>
        <Button size="sm" icon={<Download className="size-3.5" />} onClick={async () => {
          try { downloadText(`${slugify(p.name)}.prompt-studio.json`, JSON.stringify(await api.get(`/api/projects/${p.id}/bundle`), null, 2), "application/json"); } catch (e) { toast(errorMessage(e), "error"); }
        }}>Export</Button>
        {p.archived ? (
          <Button size="sm" icon={<ArchiveRestore className="size-3.5" />} onClick={() => simple(() => api.post(`/api/projects/${p.id}/restore`), "Restored")}>Restore</Button>
        ) : (
          <Button size="sm" icon={<Archive className="size-3.5" />} onClick={() => simple(() => api.post(`/api/projects/${p.id}/archive`), "Archived")}>Archive</Button>
        )}
        <Button size="sm" variant="danger" icon={<Trash2 className="size-3.5" />} onClick={() => setConfirmDelete(true)}>Delete</Button>
      </header>

      {conflict && (
        <div role="alert" className="flex flex-wrap items-center gap-2 border-b border-warn/40 bg-warn-soft px-4 py-2 text-xs text-warn">
          This project was changed elsewhere (another tab?). Your edits were not saved and are still in the form.
          <Button size="sm" onClick={() => downloadText(`${slugify(draft.name)}-unsaved-edits.json`, JSON.stringify(draft, null, 2), "application/json")}>
            Download my edits
          </Button>
          <Button size="sm" onClick={async () => {
            if (!window.confirm("Discard your unsaved edits and load the latest version?")) return;
            await project.reload();
            const fresh = await api.get<Project>(`/api/projects/${p.id}`);
            setDraft(toDraft(fresh));
            setConflict(false);
          }}>Discard mine & reload</Button>
        </div>
      )}
      {saveError && <div className="px-4 pt-2"><ErrorBanner message={saveError} /></div>}

      <div className="flex min-h-0 flex-1 max-lg:flex-col max-lg:overflow-y-auto">
        <section aria-label="Prompt workspace" className="min-w-0 flex-1 overflow-y-auto max-lg:flex-none max-lg:overflow-visible">
          <div className="sticky top-0 z-10 flex items-center justify-between gap-2 border-b border-border bg-bg/95 px-4 py-2 backdrop-blur">
            <Tabs
              label="Workspace sections"
              value={main}
              onChange={setMain}
              tabs={[
                { id: "idea", label: "Idea & context" },
                { id: "requirements", label: "Requirements", count: p.requirements.filter((r) => r.status === "confirmed").length },
                { id: "prompt", label: "Prompt" },
                { id: "versions", label: "Versions", count: projectPrompt?.version_count },
              ]}
            />
            <div className="flex items-center gap-2">
              {main === "idea" && <span className="hidden text-xs text-muted md:inline"><Kbd>⌘/Ctrl</Kbd> <Kbd>S</Kbd> to save</span>}
              <Button size="sm" variant="ghost" aria-label={sideOpen ? "Hide analysis panel" : "Show analysis panel"} icon={sideOpen ? <PanelRightClose className="size-4" /> : <PanelRightOpen className="size-4" />} onClick={() => setSideOpen(!sideOpen)} />
            </div>
          </div>
          <div className="px-4 py-4">
            {main === "idea" && <IdeaPanel draft={draft} onChange={setDraft} />}
            {main === "requirements" && <RequirementsPanel projectId={p.id} requirements={p.requirements} onChanged={reloadAll} />}
            {main === "prompt" && (
              <PromptPanel projectId={p.id} projectName={p.name} defaultProfile={p.config.target_agent} category={p.config.task_category}
                specVersion={specVersion} dirty={dirty} onSaved={() => { setVersionsKey((k) => k + 1); void reloadAll(); }} />
            )}
            {main === "versions" && (
              projectPrompt ? (
                <PromptVersions promptId={projectPrompt.id} refreshKey={versionsKey} onChanged={reloadAll} />
              ) : (
                <EmptyState title="No saved versions yet" action={<Button size="sm" onClick={() => setMain("prompt")}>Go to Prompt</Button>}>
                  Generate a variant or edit a prompt, then choose “Save version”. Each save creates an immutable version.
                </EmptyState>
              )
            )}
          </div>
        </section>

        {sideOpen && (
          <aside aria-label="Analysis and recommendations" className="flex w-[420px] shrink-0 flex-col border-l border-border bg-panel max-lg:w-full max-lg:border-t max-lg:border-l-0">
            <div className="border-b border-border px-3 py-2">
              <Tabs
                label="Analysis panels"
                size="sm"
                value={side}
                onChange={setSide}
                tabs={[
                  { id: "findings", label: "Findings", count: openFindings },
                  { id: "recommendations", label: "Recommendations", count: proposed },
                  { id: "clarify", label: "Clarify" },
                  { id: "history", label: "History" },
                ]}
              />
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
              {side === "findings" && <FindingsPanel projectId={p.id} findings={findings.data ?? []} runs={runs.data ?? []} dirty={dirty} onChanged={reloadAll} />}
              {side === "recommendations" && <RecommendationsPanel recs={recs.data ?? []} onChanged={reloadAll} />}
              {side === "clarify" && <ClarifyPanel projectId={p.id} version={historyKey} onAnswered={reloadAll} />}
              {side === "history" && <HistoryPanel projectId={p.id} version={historyKey} />}
            </div>
          </aside>
        )}
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Delete project"
        confirmLabel="Delete permanently"
        phrase={p.name}
        message={<p>This permanently deletes <strong>{p.name}</strong> including requirements, analysis, recommendations and all prompt versions.</p>}
        onConfirm={async () => {
          try {
            await api.del(`/api/projects/${p.id}?confirm=true`);
            toast("Project deleted");
            router.push("/projects");
          } catch (e) {
            toast(errorMessage(e), "error");
          }
        }}
      />
    </div>
  );
}
