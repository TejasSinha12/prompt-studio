"use client";

import { Copy, Download, Pencil, Save, Star } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Markdown } from "@/components/Markdown";
import { PromptVersions } from "@/components/PromptVersions";
import { useToast } from "@/components/Toast";
import { Button, Card, ErrorBanner, Field, Input, Select, Spinner, Tabs, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { copyText, downloadText } from "@/lib/download";
import { CATEGORY_LABELS, PROFILE_LABELS, slugify } from "@/lib/format";
import { useResource } from "@/lib/hooks";
import type { PromptDetail } from "@/lib/types";

export default function PromptDetailPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [key, setKey] = useState(0);
  const detail = useResource<PromptDetail>(`/api/prompts/${id}?k=${key}`);
  const [meta, setMeta] = useState({ title: "", category: "general", target_agent: "generic_coding", tags: "" });
  const [tab, setTab] = useState<"current" | "versions" | "edit">("current");
  const [draft, setDraft] = useState("");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const d = detail.data;

  useEffect(() => {
    if (d) setMeta({ title: d.title, category: d.category, target_agent: d.target_agent, tags: d.tags.map((t) => t.name).join(", ") });
  }, [d]);

  if (detail.error && !d) return <div className="p-6"><ErrorBanner message={detail.error} onRetry={detail.reload} /></div>;
  if (!d) return <div className="p-6"><Spinner /></div>;
  const cur = d.current_version;
  const metaDirty = meta.title !== d.title || meta.category !== d.category || meta.target_agent !== d.target_agent || meta.tags !== d.tags.map((t) => t.name).join(", ");

  async function saveMeta() {
    try {
      await api.patch(`/api/prompts/${id}`, { ...meta, title: meta.title.trim(), tags: meta.tags.split(",").map((t) => t.trim()).filter(Boolean).slice(0, 20) });
      toast("Details saved");
      setKey((k) => k + 1);
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      <nav aria-label="Breadcrumb" className="mb-1 text-xs text-muted"><Link href="/library" className="hover:text-text">Prompt Library</Link> /</nav>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="flex items-center gap-2 text-lg font-semibold">
          {d.title}
          <button type="button" aria-label={d.favorite ? "Unfavorite" : "Favorite"} aria-pressed={d.favorite}
            onClick={async () => { await api.patch(`/api/prompts/${id}`, { favorite: !d.favorite }); setKey((k) => k + 1); }}>
            <Star className={`size-4 ${d.favorite ? "fill-current text-warn" : "text-muted"}`} />
          </button>
        </h1>
        {d.project_id && <Link href={`/projects/${d.project_id}`} className="text-xs text-accent hover:underline">Open project: {d.project_name}</Link>}
      </div>

      <Card className="mb-4 grid gap-3 p-3 md:grid-cols-5">
        <Field label="Title" className="md:col-span-2">{(fid) => <Input id={fid} value={meta.title} maxLength={200} onChange={(e) => setMeta({ ...meta, title: e.target.value })} />}</Field>
        <Field label="Category">{(fid) => (
          <Select id={fid} value={meta.category} onChange={(e) => setMeta({ ...meta, category: e.target.value })}>
            {Object.entries(CATEGORY_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>)}
        </Field>
        <Field label="Target agent">{(fid) => (
          <Select id={fid} value={meta.target_agent} onChange={(e) => setMeta({ ...meta, target_agent: e.target.value })}>
            {Object.entries(PROFILE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>)}
        </Field>
        <Field label="Tags">{(fid) => <Input id={fid} value={meta.tags} onChange={(e) => setMeta({ ...meta, tags: e.target.value })} />}</Field>
        {metaDirty && <div className="flex justify-end md:col-span-5"><Button size="sm" variant="primary" disabled={!meta.title.trim()} onClick={saveMeta}>Save details</Button></div>}
      </Card>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Tabs label="Prompt views" value={tab} onChange={(t) => { setTab(t); if (t === "edit") setDraft(cur?.content ?? ""); }}
          tabs={[{ id: "current", label: `Current${cur ? ` (v${cur.number})` : ""}` }, { id: "versions", label: "Versions & diff", count: d.versions.length }, { id: "edit", label: "Edit" }]} />
        {cur && (
          <div className="flex gap-1.5">
            <Button size="sm" icon={<Copy className="size-3" />} onClick={async () => toast((await copyText(cur.content)) ? "Copied" : "Copy failed", "info")}>Copy</Button>
            <Button size="sm" icon={<Download className="size-3" />} onClick={() => downloadText(`${slugify(d.title)}-v${cur.number}.md`, cur.content, "text/markdown")}>.md</Button>
            <Button size="sm" icon={<Download className="size-3" />} onClick={async () => {
              if (d.project_id) {
                try { const f = await api.post<{ content: string; filename: string }>(`/api/projects/${d.project_id}/export`, { format: "text", version_id: cur.id }); downloadText(f.filename, f.content); } catch (e) { toast(errorMessage(e), "error"); }
              } else downloadText(`${slugify(d.title)}-v${cur.number}.txt`, cur.content);
            }}>.txt</Button>
            <Button size="sm" icon={<Pencil className="size-3" />} onClick={() => { setDraft(cur.content); setTab("edit"); }}>Edit</Button>
          </div>
        )}
      </div>

      {tab === "current" && cur && <Card className="p-4"><Markdown content={cur.content} /></Card>}
      {tab === "versions" && <PromptVersions promptId={d.id} refreshKey={key} onChanged={() => setKey((k) => k + 1)} />}
      {tab === "edit" && (
        <div className="flex flex-col gap-2">
          <div className="grid gap-3 lg:grid-cols-2">
            <Textarea aria-label="Prompt content" value={draft} onChange={(e) => setDraft(e.target.value)} className="min-h-[60vh] font-mono text-[12.5px]" />
            <Card className="max-h-[60vh] min-h-[60vh] overflow-y-auto p-3"><Markdown content={draft} /></Card>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Input aria-label="Change summary" placeholder="Change summary (optional)" value={summary} onChange={(e) => setSummary(e.target.value)} className="w-72" />
            <Button onClick={() => setTab("current")}>Cancel</Button>
            <Button variant="primary" icon={<Save className="size-3.5" />} busy={busy} disabled={!draft.trim() || draft === cur?.content}
              onClick={async () => {
                setBusy(true);
                try {
                  await api.post(`/api/prompts/${id}/versions`, { content: draft, variant: "manual", generator: "manual", change_summary: summary });
                  toast("Saved as a new version");
                  setSummary("");
                  setKey((k) => k + 1);
                  setTab("versions");
                } catch (e) { toast(errorMessage(e), "error"); } finally { setBusy(false); }
              }}>
              Save as new version
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
