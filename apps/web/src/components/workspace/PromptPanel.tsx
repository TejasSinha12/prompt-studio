"use client";

import { AlertTriangle, CheckCircle2, Copy, Download, FileArchive, FolderOutput, Pencil, RefreshCw, Save, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { copyText, downloadBlob, downloadText } from "@/lib/download";
import { PROFILE_LABELS, slugify } from "@/lib/format";
import { useDebounced, useResource } from "@/lib/hooks";
import { useJob } from "@/lib/jobs";
import type { BuildResult, Evaluation, ExportFile, ExportFormat, OptimizeResult, Page, PreservationItem, PromptSummary, Variant } from "@/lib/types";
import { useApp } from "../AppContext";
import { DiffView } from "../DiffView";
import { Markdown } from "../Markdown";
import { useToast } from "../Toast";
import { Badge, Button, Card, EngineBadge, Input, Notice, Select, Spinner, Tabs, Textarea } from "../ui";
import { AiJobStatus } from "./AiJobStatus";
import { HandoffDialog } from "./HandoffDialog";

interface EditorState {
  content: string;
  original: string;
  variant: Variant | "manual";
  generator: "rule_based" | "local_ai" | "manual";
  model: string | null;
}

const ZIP_FORMATS = ["markdown", "claude_md", "agents_md", "cursor_mdc", "plan", "tasks", "tests", "spec"];

export function PromptPanel({
  projectId,
  projectName,
  defaultProfile,
  category,
  specVersion,
  dirty,
  onSaved,
}: {
  projectId: string;
  projectName: string;
  defaultProfile: string;
  category: string;
  specVersion: string;
  dirty: boolean;
  onSaved: () => void;
}) {
  const toast = useToast();
  const { aiReady, aiUnavailableReason } = useApp();
  const [profile, setProfile] = useState(defaultProfile);
  const [results, setResults] = useState<BuildResult[] | null>(null);
  const [builtFrom, setBuiltFrom] = useState<string>("");
  const [genBusy, setGenBusy] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [layout, setLayout] = useState<"compare" | "single">("compare");
  const [selected, setSelected] = useState<Variant>("balanced");
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [aiResult, setAiResult] = useState<OptimizeResult | null>(null);
  const prompts = useResource<Page<PromptSummary>>(`/api/prompts?project_id=${projectId}&archived=all&limit=50`);
  const projectPrompt = prompts.data?.items[0] ?? null;

  const ai = useJob((j) => {
    if (j.status === "succeeded" && j.result) setAiResult(j.result as unknown as OptimizeResult);
  });

  useEffect(() => setProfile(defaultProfile), [defaultProfile]);

  const generate = useCallback(async () => {
    setGenBusy(true);
    setGenError(null);
    try {
      const out = await api.post<{ results: BuildResult[] }>(`/api/projects/${projectId}/generate`, { profile_id: profile });
      setResults(out.results);
      setBuiltFrom(specVersion);
    } catch (e) {
      setGenError(errorMessage(e));
    } finally {
      setGenBusy(false);
    }
  }, [projectId, profile, specVersion]);

  useEffect(() => {
    void generate();
    // Generate once on open and whenever the profile changes; spec changes show a "stale" notice instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, profile]);

  async function saveVersion(content: string, variant: Variant | "manual", generator: EditorState["generator"], model: string | null, summary: string) {
    try {
      if (projectPrompt) {
        await api.post(`/api/prompts/${projectPrompt.id}/versions`, { content, variant, generator, model, profile_id: profile, change_summary: summary });
      } else {
        await api.post("/api/prompts", {
          project_id: projectId,
          title: projectName,
          category,
          target_agent: profile,
          content,
          variant,
          generator,
          model,
          change_summary: summary || "Initial version",
        });
      }
      toast("Saved as a new version");
      await prompts.reload();
      onSaved();
      return true;
    } catch (e) {
      toast(errorMessage(e), "error");
      return false;
    }
  }

  const stale = results !== null && builtFrom !== specVersion;
  const current = results?.find((r) => r.variant === selected) ?? null;

  if (editor) {
    return (
      <PromptEditor
        projectId={projectId}
        state={editor}
        coding={category !== "writing" && category !== "general" && profile !== "generic_llm"}
        onCancel={() => setEditor(null)}
        onSave={async (content, summary) => {
          const generator = content === editor.original ? editor.generator : "manual";
          const ok = await saveVersion(content, generator === "manual" ? "manual" : editor.variant, generator, generator === "local_ai" ? editor.model : null, summary);
          if (ok) setEditor(null);
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-muted" htmlFor="profile-select">Target profile</label>
        <Select id="profile-select" value={profile} onChange={(e) => setProfile(e.target.value)} className="w-48">
          {Object.entries(PROFILE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </Select>
        <Button size="sm" icon={<RefreshCw className="size-3.5" />} busy={genBusy} onClick={generate}>
          {results ? "Regenerate" : "Generate"}
        </Button>
        <div className="ml-auto">
          <Tabs label="Variant layout" size="sm" value={layout} onChange={setLayout} tabs={[{ id: "compare", label: "Side by side" }, { id: "single", label: "Single" }]} />
        </div>
      </div>
      {dirty && <Notice tone="warn">Unsaved edits are not included. Save the project, then regenerate.</Notice>}
      {stale && !dirty && (
        <Notice tone="warn">
          The specification changed since these variants were generated.{" "}
          <button type="button" className="font-medium underline" onClick={generate}>Regenerate</button>
        </Notice>
      )}
      {genError && <Notice tone="danger">{genError}</Notice>}
      {!results && genBusy && <Spinner label="Generating" />}
      {results && (
        <>
          <p className="text-xs text-muted">
            Three deterministic variants built from the confirmed specification. None is “optimal” — pick the one that fits the task. Sections marked{" "}
            <Badge>template</Badge> contain generic guidance written by Prompt Studio, not by you.
          </p>
          {layout === "compare" ? (
            <div className="grid gap-3 xl:grid-cols-3">
              {results.map((r) => (
                <VariantCard key={r.variant} r={r} compact onEdit={() => setEditor({ content: r.content, original: r.content, variant: r.variant, generator: "rule_based", model: null })}
                  onSave={() => saveVersion(r.content, r.variant, "rule_based", null, `Generated ${r.variant} variant (${PROFILE_LABELS[r.profile_id] ?? r.profile_id} v${r.profile_version})`)}
                  onRefine={aiReady ? () => { setSelected(r.variant); setAiResult(null); void ai.start({ kind: "optimize", project_id: projectId, variant: r.variant, profile_id: profile }); } : undefined}
                  refineDisabledReason={aiUnavailableReason} aiRunning={ai.running} />
              ))}
            </div>
          ) : (
            <>
              <Tabs label="Variant" value={selected} onChange={setSelected} tabs={results.map((r) => ({ id: r.variant, label: r.variant[0]!.toUpperCase() + r.variant.slice(1) }))} />
              {current && (
                <VariantCard r={current} onEdit={() => setEditor({ content: current.content, original: current.content, variant: current.variant, generator: "rule_based", model: null })}
                  onSave={() => saveVersion(current.content, current.variant, "rule_based", null, `Generated ${current.variant} variant`)}
                  onRefine={aiReady ? () => { setAiResult(null); void ai.start({ kind: "optimize", project_id: projectId, variant: current.variant, profile_id: profile }); } : undefined}
                  refineDisabledReason={aiUnavailableReason} aiRunning={ai.running} />
              )}
            </>
          )}
        </>
      )}

      <AiJobStatus job={ai.job} running={ai.running} error={ai.error} onCancel={ai.cancel} />
      {aiResult && (
        <Card className="p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h3 className="flex items-center gap-2 text-[13px] font-semibold">
              Local AI refinement of the {aiResult.variant} variant <EngineBadge engine="local_ai" model={aiResult.model} />
            </h3>
            <div className="flex gap-1.5">
              <Button size="sm" onClick={() => setAiResult(null)}>Discard</Button>
              <Button size="sm" icon={<Pencil className="size-3" />} onClick={() => { setEditor({ content: aiResult.content, original: aiResult.content, variant: aiResult.variant, generator: "local_ai", model: aiResult.model }); setAiResult(null); }}>
                Edit before saving
              </Button>
              <Button size="sm" variant="primary" icon={<Save className="size-3" />}
                onClick={async () => { if (await saveVersion(aiResult.content, aiResult.variant, "local_ai", aiResult.model, `Local AI refinement (${aiResult.model}) of ${aiResult.variant} variant`)) setAiResult(null); }}>
                Save as version
              </Button>
            </div>
          </div>
          {aiResult.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
          <PreservationList items={aiResult.preservation} />
          {aiResult.rejected_reintroduced.length > 0 && (
            <Notice tone="danger">Reintroduced rejected items: {aiResult.rejected_reintroduced.join("; ")}</Notice>
          )}
          <div className="mt-2">
            <DiffView before={aiResult.base_content} after={aiResult.content} beforeLabel="Rule-based variant" afterLabel="Local AI refinement" />
          </div>
        </Card>
      )}

      <ExportBox projectId={projectId} projectName={projectName} profile={profile} versionId={projectPrompt?.current_version_id ?? null} fallback={current?.content ?? results?.[1]?.content ?? ""} />
    </div>
  );
}

function VariantCard({
  r,
  compact = false,
  onEdit,
  onSave,
  onRefine,
  refineDisabledReason,
  aiRunning,
}: {
  r: BuildResult;
  compact?: boolean;
  onEdit: () => void;
  onSave: () => void;
  onRefine?: () => void;
  refineDisabledReason: string;
  aiRunning: boolean;
}) {
  const toast = useToast();
  const [raw, setRaw] = useState(false);
  const preserved = r.preservation.filter((p) => p.preserved).length;
  const templateSections = r.sections.filter((s) => s.source === "template").length;
  return (
    <Card className="flex min-w-0 flex-col">
      <div className="flex flex-col gap-1.5 border-b border-border px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-[13px] font-semibold capitalize">{r.variant}</h3>
          <EngineBadge engine="rule_based" />
        </div>
        <p className="text-xs text-muted">
          {r.word_count} words · {r.char_count} chars · ≈{r.token_estimate} tokens <span title="Approximation: max(chars/4, words×1.3). Not a tokenizer count.">(estimate)</span>
        </p>
        <p className={`flex items-center gap-1 text-xs ${preserved === r.preservation.length ? "text-ok" : "text-danger"}`}>
          {preserved === r.preservation.length ? <CheckCircle2 className="size-3.5" aria-hidden /> : <AlertTriangle className="size-3.5" aria-hidden />}
          {r.preservation.length === 0 ? "No confirmed requirements to preserve" : `${preserved}/${r.preservation.length} confirmed requirements preserved`}
        </p>
        {templateSections > 0 && <p className="text-xs text-muted">{templateSections} section(s) with template guidance: {r.sections.filter((s) => s.source === "template").map((s) => s.title).join(", ")}</p>}
        {r.warnings.map((w) => <p key={w} className="text-xs text-warn">{w}</p>)}
      </div>
      <div className={`overflow-y-auto px-3 py-2 ${compact ? "max-h-[460px]" : "max-h-[65vh]"}`}>
        {raw ? <pre className="font-mono text-[12px] whitespace-pre-wrap">{r.content}</pre> : <Markdown content={r.content} />}
      </div>
      <div className="mt-auto flex flex-wrap gap-1.5 border-t border-border px-3 py-2">
        <Button size="sm" variant="ghost" onClick={() => setRaw(!raw)} aria-pressed={raw}>{raw ? "Preview" : "Raw"}</Button>
        <Button size="sm" icon={<Copy className="size-3" />} onClick={async () => toast((await copyText(r.content)) ? "Copied to clipboard" : "Copy failed", "info")}>Copy</Button>
        <Button size="sm" icon={<Pencil className="size-3" />} onClick={onEdit}>Edit</Button>
        <Button size="sm" icon={<Sparkles className="size-3" />} disabled={!onRefine || aiRunning} title={onRefine ? "Refine with the local model" : refineDisabledReason} onClick={onRefine}>Refine (AI)</Button>
        <Button size="sm" variant="primary" icon={<Save className="size-3" />} onClick={onSave}>Save version</Button>
      </div>
    </Card>
  );
}

export function PreservationList({ items }: { items: PreservationItem[] }) {
  const missing = items.filter((p) => !p.preserved);
  if (items.length === 0) return null;
  if (missing.length === 0)
    return <p className="flex items-center gap-1 text-xs text-ok"><CheckCircle2 className="size-3.5" aria-hidden /> All {items.length} confirmed requirements are present verbatim.</p>;
  return (
    <div className="rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-xs text-danger">
      <p className="font-medium">{missing.length} confirmed requirement(s) not present verbatim:</p>
      <ul className="mt-1 list-disc pl-4">
        {missing.map((m) => <li key={m.requirement_id}>{m.text} <span className="opacity-75">({Math.round(m.coverage * 100)}% of words present)</span></li>)}
      </ul>
    </div>
  );
}

function PromptEditor({
  projectId,
  state,
  coding,
  onCancel,
  onSave,
}: {
  projectId: string;
  state: EditorState;
  coding: boolean;
  onCancel: () => void;
  onSave: (content: string, summary: string) => Promise<void>;
}) {
  const [content, setContent] = useState(state.content);
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [preservation, setPreservation] = useState<PreservationItem[]>([]);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const dc = useDebounced(content, 500);
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.post<PreservationItem[]>(`/api/projects/${projectId}/preservation`, { content: dc }),
      api.post<Evaluation>("/api/evaluate-text", { content: dc, coding }),
    ])
      .then(([p, e]) => {
        if (!cancelled) {
          setPreservation(p);
          setEvaluation(e);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [dc, projectId, coding]);
  const changed = content !== state.original;
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => {
      if (changed) e.preventDefault();
    };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [changed]);
  const onKey = useMemo(
    () => (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (content.trim()) void (async () => { setBusy(true); await onSave(content, summary); setBusy(false); })();
      }
    },
    [content, summary, onSave],
  );
  return (
    <div className="flex flex-col gap-3" onKeyDown={onKey}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-[13px] font-semibold">
          Manual editing <EngineBadge engine={changed ? "manual" : state.generator} model={state.model} />
        </h3>
        <div className="flex items-center gap-2">
          <Input aria-label="Change summary" placeholder="Change summary (optional)" value={summary} onChange={(e) => setSummary(e.target.value)} className="w-64" maxLength={1000} />
          <Button onClick={() => { if (!changed || window.confirm("Discard your edits?")) onCancel(); }}>Cancel</Button>
          <Button variant="primary" icon={<Save className="size-3.5" />} busy={busy} disabled={!content.trim()}
            onClick={async () => { setBusy(true); await onSave(content, summary); setBusy(false); }}>
            Save as version
          </Button>
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Textarea aria-label="Prompt content" value={content} onChange={(e) => setContent(e.target.value)} className="min-h-[60vh] font-mono text-[12.5px]" spellCheck />
        <div className="max-h-[60vh] min-h-[60vh] overflow-y-auto rounded-md border border-border bg-panel p-3">
          <Markdown content={content} />
        </div>
      </div>
      <PreservationList items={preservation} />
      {evaluation && (
        <div className="rounded-md border border-border bg-panel px-3 py-2 text-xs">
          <p className="mb-1 font-medium">
            Live rule-based diagnostics · heuristic score {evaluation.score ?? "—"}/100 <span className="font-normal text-muted">({evaluation.metrics.token_estimate} tokens, estimate)</span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {evaluation.dimensions.filter((d) => d.score !== null).map((d) => (
              <Badge key={d.id} tone={d.score! >= 80 ? "ok" : d.score! >= 50 ? "warn" : "danger"} title={d.summary}>{d.name}: {Math.round(d.score!)}</Badge>
            ))}
          </div>
        </div>
      )}
      {changed && (
        <details className="text-xs">
          <summary className="cursor-pointer text-muted">Show changes from the starting text</summary>
          <div className="mt-2"><DiffView before={state.original} after={content} beforeLabel="Start" afterLabel="Edited" /></div>
        </details>
      )}
    </div>
  );
}

function ExportBox({ projectId, projectName, profile, versionId, fallback }: { projectId: string; projectName: string; profile: string; versionId: string | null; fallback: string }) {
  const [handoff, setHandoff] = useState(false);
  const toast = useToast();
  const formats = useResource<ExportFormat[]>("/api/export-formats");
  const [fmt, setFmt] = useState("markdown");
  const [source, setSource] = useState<"version" | "variant">(versionId ? "version" : "variant");
  const [busy, setBusy] = useState(false);
  useEffect(() => setSource(versionId ? "version" : "variant"), [versionId]);
  const body = source === "version" && versionId ? { version_id: versionId } : { content: fallback };

  async function get(): Promise<ExportFile> {
    return api.post<ExportFile>(`/api/projects/${projectId}/export`, { format: fmt, ...body });
  }
  return (
    <Card className="p-3">
      <h3 className="mb-2 text-[13px] font-semibold">Export</h3>
      <div className="flex flex-wrap items-center gap-2">
        <Select aria-label="Export format" value={fmt} onChange={(e) => setFmt(e.target.value)} className="w-56">
          {(formats.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
        </Select>
        <Select aria-label="Export source" value={source} onChange={(e) => setSource(e.target.value as typeof source)} className="w-56">
          <option value="version" disabled={!versionId}>Current saved version{versionId ? "" : " (none yet)"}</option>
          <option value="variant">Selected/balanced variant (unsaved)</option>
        </Select>
        <Button size="sm" icon={<Download className="size-3" />} busy={busy} onClick={async () => {
          setBusy(true);
          try { const f = await get(); downloadText(f.filename, f.content, f.media_type); } catch (e) { toast(errorMessage(e), "error"); } finally { setBusy(false); }
        }}>Download</Button>
        <Button size="sm" icon={<Copy className="size-3" />} onClick={async () => {
          try { const f = await get(); toast((await copyText(f.content)) ? `Copied ${f.filename}` : "Copy failed", "info"); } catch (e) { toast(errorMessage(e), "error"); }
        }}>Copy</Button>
        <Button size="sm" icon={<FileArchive className="size-3" />} onClick={async () => {
          try { downloadBlob(`${slugify(projectName)}-agent-files.zip`, await api.blob(`/api/projects/${projectId}/export.zip`, { formats: ZIP_FORMATS, ...body })); } catch (e) { toast(errorMessage(e), "error"); }
        }}>All agent files (.zip)</Button>
        <Button size="sm" icon={<FolderOutput className="size-3" />} onClick={() => setHandoff(true)}>Hand off to agent…</Button>
      </div>
      {handoff && <HandoffDialog open onClose={() => setHandoff(false)} projectId={projectId} defaultProfile={profile} source={body} />}
      <p className="mt-1.5 text-xs text-muted">Exports are generated locally and never include settings or the Ollama endpoint. Instruction files (CLAUDE.md, AGENTS.md, .mdc) contain stable project conventions from confirmed requirements.</p>
    </Card>
  );
}
