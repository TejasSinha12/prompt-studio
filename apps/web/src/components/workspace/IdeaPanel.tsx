"use client";

import { FolderSearch } from "lucide-react";
import { useState } from "react";
import { CATEGORY_LABELS, PROFILE_LABELS } from "@/lib/format";
import type { PromptConfig } from "@/lib/types";
import { Markdown } from "../Markdown";
import { Button, Field, Input, Select, Tabs, Textarea } from "../ui";
import { CodebaseDialog } from "./CodebaseDialog";

export interface ProjectDraft {
  name: string;
  description: string;
  original_idea: string;
  tech_stack: string;
  tags: string;
  config: PromptConfig;
}

const TEXT_FIELDS: { key: keyof PromptConfig; label: string; hint?: string; multiline?: boolean }[] = [
  { key: "language", label: "Programming language" },
  { key: "framework", label: "Framework" },
  { key: "tone", label: "Tone", hint: "e.g. direct, formal" },
  { key: "output_format", label: "Output format / deliverables", hint: "What the agent should return" },
  { key: "testing", label: "Testing expectations", multiline: true },
  { key: "security", label: "Security requirements", multiline: true },
  { key: "performance", label: "Performance constraints", multiline: true, hint: "Prefer measurable targets" },
  { key: "hardware", label: "Hardware constraints" },
  { key: "budget", label: "Budget constraints" },
  { key: "architecture", label: "Preferred architecture", multiline: true },
  { key: "restrictions", label: "Additional restrictions", multiline: true, hint: "What must not be done or changed" },
  { key: "existing_codebase", label: "Existing codebase information", multiline: true, hint: "Structure, conventions, relevant files" },
];

export function IdeaPanel({ draft, onChange }: { draft: ProjectDraft; onChange: (d: ProjectDraft) => void }) {
  const [ideaView, setIdeaView] = useState<"write" | "preview">("write");
  const [codebaseOpen, setCodebaseOpen] = useState(false);
  const set = <K extends keyof ProjectDraft>(k: K, v: ProjectDraft[K]) => onChange({ ...draft, [k]: v });
  const setCfg = (k: keyof PromptConfig, v: string) => onChange({ ...draft, config: { ...draft.config, [k]: v } });
  return (
    <div className="flex flex-col gap-5">
      <section aria-labelledby="idea-h" className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 id="idea-h" className="text-[13px] font-semibold">Original idea</h3>
          <Tabs label="Idea view" size="sm" value={ideaView} onChange={setIdeaView} tabs={[{ id: "write", label: "Write" }, { id: "preview", label: "Preview" }]} />
        </div>
        {ideaView === "write" ? (
          <Textarea
            aria-label="Original idea"
            rows={10}
            className="font-mono text-[12.5px]"
            placeholder="Describe the idea in your own words. Markdown is supported. Partial input is fine — analysis will point out what is missing."
            value={draft.original_idea}
            onChange={(e) => set("original_idea", e.target.value)}
          />
        ) : (
          <div className="min-h-40 rounded-md border border-border bg-panel p-3">
            {draft.original_idea.trim() ? <Markdown content={draft.original_idea} /> : <p className="text-xs text-muted">Nothing to preview.</p>}
          </div>
        )}
        <p className="text-xs text-muted">{draft.original_idea.trim().split(/\s+/).filter(Boolean).length} words</p>
      </section>

      <section aria-labelledby="ctx-h" className="grid gap-3 md:grid-cols-2">
        <h3 id="ctx-h" className="text-[13px] font-semibold md:col-span-2">Project context</h3>
        <Field label="Project name" className="md:col-span-2">
          {(id) => <Input id={id} value={draft.name} maxLength={200} onChange={(e) => set("name", e.target.value)} />}
        </Field>
        <Field label="Description" className="md:col-span-2">
          {(id) => <Textarea id={id} rows={2} value={draft.description} onChange={(e) => set("description", e.target.value)} />}
        </Field>
        <Field label="Technology stack" hint="Comma-separated or free text">
          {(id) => <Input id={id} value={draft.tech_stack} onChange={(e) => set("tech_stack", e.target.value)} />}
        </Field>
        <Field label="Tags" hint="Comma-separated, max 20">
          {(id) => <Input id={id} value={draft.tags} onChange={(e) => set("tags", e.target.value)} />}
        </Field>
      </section>

      <section aria-labelledby="cfg-h" className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <h3 id="cfg-h" className="text-[13px] font-semibold md:col-span-2 xl:col-span-4">
          Prompt configuration <span className="font-normal text-muted">— all optional</span>
        </h3>
        <Field label="Target agent">
          {(id) => (
            <Select id={id} value={draft.config.target_agent} onChange={(e) => setCfg("target_agent", e.target.value)}>
              {Object.entries(PROFILE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Task category">
          {(id) => (
            <Select id={id} value={draft.config.task_category} onChange={(e) => setCfg("task_category", e.target.value)}>
              {Object.entries(CATEGORY_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Project size">
          {(id) => (
            <Select id={id} value={draft.config.project_size} onChange={(e) => setCfg("project_size", e.target.value)}>
              <option value="">Not specified</option>
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
            </Select>
          )}
        </Field>
        <Field label="Detail level">
          {(id) => (
            <Select id={id} value={draft.config.detail_level} onChange={(e) => setCfg("detail_level", e.target.value)}>
              <option value="">Not specified</option>
              <option value="concise">Concise</option>
              <option value="balanced">Balanced</option>
              <option value="detailed">Detailed</option>
            </Select>
          )}
        </Field>
        {TEXT_FIELDS.map((f) => (
          <Field key={f.key} label={f.label} hint={f.hint} className={f.multiline ? "md:col-span-2" : undefined}>
            {(id) =>
              f.multiline ? (
                <Textarea id={id} rows={2} value={draft.config[f.key] as string} onChange={(e) => setCfg(f.key, e.target.value)} />
              ) : (
                <Input id={id} value={draft.config[f.key] as string} onChange={(e) => setCfg(f.key, e.target.value)} />
              )
            }
          </Field>
        ))}
        <div className="flex items-center gap-2 md:col-span-2 xl:col-span-4">
          <Button size="sm" icon={<FolderSearch className="size-3.5" />} onClick={() => setCodebaseOpen(true)}>
            Add context from a local codebase…
          </Button>
          <span className="text-xs text-muted">Read-only scan of a directory you choose; fills “Existing codebase information”.</span>
        </div>
      </section>
      <CodebaseDialog
        open={codebaseOpen}
        onClose={() => setCodebaseOpen(false)}
        onInsert={(md) => {
          const cur = draft.config.existing_codebase.trim();
          setCfg("existing_codebase", cur ? `${cur}\n\n${md}` : md);
        }}
      />
    </div>
  );
}
