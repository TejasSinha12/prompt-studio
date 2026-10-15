"use client";

import { Archive, ArchiveRestore, Copy, FileUp, Library, Search, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";
import { Badge, Button, Card, EmptyState, ErrorBanner, IconButton, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, errorMessage, qs } from "@/lib/api";
import { readFileText } from "@/lib/download";
import { CATEGORY_LABELS, categoryLabel, PROFILE_LABELS, relativeTime } from "@/lib/format";
import { useDebounced, useResource } from "@/lib/hooks";
import type { Page, PromptDetail, PromptSummary } from "@/lib/types";

const MAX_MD = 1024 * 1024;

export default function LibraryPage() {
  const router = useRouter();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [category, setCategory] = useState("");
  const [fav, setFav] = useState(false);
  const [archived, setArchived] = useState<"false" | "true" | "all">("false");
  const dq = useDebounced(q, 250);
  const list = useResource<Page<PromptSummary>>(`/api/prompts${qs({ q: dq, tag, category, favorite: fav ? true : undefined, archived, limit: 200 })}`);
  const [toDelete, setToDelete] = useState<PromptSummary | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const tags = Array.from(new Set((list.data?.items ?? []).flatMap((p) => p.tags.map((t) => t.name)))).sort();

  async function act(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn();
      toast(ok);
      await list.reload();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  async function importMarkdown(file: File) {
    try {
      const content = await readFileText(file, MAX_MD);
      if (!content.trim()) throw new Error("The file is empty.");
      const title = file.name.replace(/\.(md|markdown|txt)$/i, "").slice(0, 200) || "Imported prompt";
      const p = await api.post<PromptDetail>("/api/prompts", { title, content, variant: "manual", generator: "manual", change_summary: `Imported from ${file.name}` });
      toast(`Imported "${p.title}"`);
      router.push(`/library/${p.id}`);
    } catch (e) {
      toast(`Import failed: ${errorMessage(e)}`, "error");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <PageHeader
        title="Prompt Library"
        description="Saved prompts with immutable version history. Search covers titles and prompt content."
        actions={
          <>
            <input ref={fileRef} type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" className="hidden" aria-label="Import Markdown prompt file"
              onChange={(e) => e.target.files?.[0] && importMarkdown(e.target.files[0])} />
            <Button icon={<FileUp className="size-4" />} onClick={() => fileRef.current?.click()}>Import Markdown</Button>
          </>
        }
      />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-60 flex-1">
          <Search className="pointer-events-none absolute top-2.5 left-2.5 size-3.5 text-muted" aria-hidden />
          <Input aria-label="Search prompts" placeholder="Search titles and content…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-8" />
        </div>
        <Select aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)} className="w-40">
          <option value="">All categories</option>
          {Object.entries(CATEGORY_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </Select>
        <Select aria-label="Tag" value={tag} onChange={(e) => setTag(e.target.value)} className="w-36">
          <option value="">All tags</option>
          {tags.map((t) => <option key={t} value={t}>{t}</option>)}
        </Select>
        <Select aria-label="Archive filter" value={archived} onChange={(e) => setArchived(e.target.value as typeof archived)} className="w-32">
          <option value="false">Active</option>
          <option value="true">Archived</option>
          <option value="all">All</option>
        </Select>
        <Button aria-pressed={fav} icon={<Star className={`size-3.5 ${fav ? "fill-current text-warn" : ""}`} />} onClick={() => setFav(!fav)}>Favorites</Button>
      </div>
      {list.error && <ErrorBanner message={list.error} onRetry={list.reload} />}
      <Card>
        {!list.data ? (
          <div className="p-6"><Spinner /></div>
        ) : list.data.items.length === 0 ? (
          <EmptyState icon={<Library className="size-6" />} title={q || tag || category || fav ? "No matching prompts" : "Your library is empty"}>
            Save a prompt version from a project workspace, or import a Markdown file.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-border">
            {list.data.items.map((p) => (
              <li key={p.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-panel-2/60">
                <IconButton label={p.favorite ? `Unfavorite ${p.title}` : `Favorite ${p.title}`} aria-pressed={p.favorite}
                  onClick={() => act(() => api.patch(`/api/prompts/${p.id}`, { favorite: !p.favorite }), p.favorite ? "Removed from favorites" : "Added to favorites")}>
                  <Star className={`size-4 ${p.favorite ? "fill-current text-warn" : ""}`} />
                </IconButton>
                <div className="min-w-0 flex-1">
                  <Link href={`/library/${p.id}`} className="text-[13px] font-medium hover:text-accent">{p.title}</Link>
                  {p.archived && <Badge className="ml-2">Archived</Badge>}
                  <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted">
                    <span>{categoryLabel(p.category)}</span>·<span>{PROFILE_LABELS[p.target_agent] ?? p.target_agent}</span>·
                    <span>{p.version_count} version(s)</span>
                    {p.project_name && <>·<Link className="hover:text-text" href={`/projects/${p.project_id}`}>{p.project_name}</Link></>}
                    {p.tags.map((t) => <Badge key={t.id}>{t.name}</Badge>)}
                  </div>
                </div>
                <span className="hidden text-xs text-muted sm:inline">{relativeTime(p.updated_at)}</span>
                <IconButton label={`Duplicate ${p.title}`} onClick={() => act(() => api.post(`/api/prompts/${p.id}/duplicate`), "Duplicated")}><Copy className="size-3.5" /></IconButton>
                <IconButton label={p.archived ? `Restore ${p.title}` : `Archive ${p.title}`} onClick={() => act(() => api.patch(`/api/prompts/${p.id}`, { archived: !p.archived }), p.archived ? "Restored" : "Archived")}>
                  {p.archived ? <ArchiveRestore className="size-3.5" /> : <Archive className="size-3.5" />}
                </IconButton>
                <IconButton label={`Delete ${p.title}`} onClick={() => setToDelete(p)} className="hover:text-danger"><Trash2 className="size-3.5" /></IconButton>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <ConfirmDialog
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        title="Delete prompt"
        confirmLabel="Delete permanently"
        message={<p>Delete <strong>{toDelete?.title}</strong> and all {toDelete?.version_count} of its versions? This cannot be undone except from a database backup.</p>}
        onConfirm={() => {
          const p = toDelete;
          setToDelete(null);
          if (p) void act(() => api.del(`/api/prompts/${p.id}?confirm=true`), "Prompt deleted");
        }}
      />
    </div>
  );
}
