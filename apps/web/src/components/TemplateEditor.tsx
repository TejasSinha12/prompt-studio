"use client";

import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { CATEGORY_LABELS, REQ_KIND_LABELS, REQ_KINDS } from "@/lib/format";
import type { ReqKind, TaskTemplate } from "@/lib/types";
import { Button, Dialog, Field, IconButton, Input, Select, Textarea } from "./ui";

export interface TemplateDraft {
  name: string;
  description: string;
  category: string;
  idea: string;
  config: Record<string, string>;
  requirements: { kind: ReqKind; text: string }[];
}

export function emptyTemplate(): TemplateDraft {
  return { name: "", description: "", category: "feature", idea: "", config: {}, requirements: [] };
}

export function fromTemplate(t: TaskTemplate): TemplateDraft {
  return { name: t.name, description: t.description, category: t.category, idea: t.idea, config: { ...t.config }, requirements: t.requirements.map((r) => ({ ...r })) };
}

/** Create or edit a custom task template. */
export function TemplateEditor({
  open,
  initial,
  title,
  busy,
  error,
  onClose,
  onSave,
}: {
  open: boolean;
  initial: TemplateDraft;
  title: string;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (t: TemplateDraft) => void;
}) {
  const [t, setT] = useState(initial);
  useEffect(() => setT(initial), [initial]);
  const setReq = (i: number, patch: Partial<TemplateDraft["requirements"][number]>) =>
    setT({ ...t, requirements: t.requirements.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const valid = t.name.trim() && t.requirements.every((r) => r.text.trim());
  return (
    <Dialog open={open} onClose={onClose} title={title} wide
      footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" busy={busy} disabled={!valid} onClick={() => onSave({ ...t, name: t.name.trim(), category: t.category, config: { ...t.config, task_category: t.category } })}>Save template</Button></>}>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Name">{(id) => <Input id={id} value={t.name} maxLength={200} onChange={(e) => setT({ ...t, name: e.target.value })} />}</Field>
        <Field label="Category">{(id) => (
          <Select id={id} value={t.category} onChange={(e) => setT({ ...t, category: e.target.value })}>
            {Object.entries(CATEGORY_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>)}
        </Field>
        <Field label="Description" className="md:col-span-2">{(id) => <Input id={id} value={t.description} onChange={(e) => setT({ ...t, description: e.target.value })} />}</Field>
        <Field label="Idea skeleton" hint="Use [brackets] for parts to fill in" className="md:col-span-2">
          {(id) => <Textarea id={id} rows={4} className="font-mono text-xs" value={t.idea} onChange={(e) => setT({ ...t, idea: e.target.value })} />}
        </Field>
        <div className="md:col-span-2">
          <p className="mb-1 text-xs font-medium text-muted">Requirements (created as “proposed” in new projects, so they are always reviewed)</p>
          <ul className="flex flex-col gap-1.5">
            {t.requirements.map((r, i) => (
              <li key={i} className="flex items-start gap-2">
                <Select aria-label={`Requirement ${i + 1} type`} value={r.kind} onChange={(e) => setReq(i, { kind: e.target.value as ReqKind })} className="w-44 shrink-0">
                  {REQ_KINDS.map((k) => <option key={k} value={k}>{REQ_KIND_LABELS[k]}</option>)}
                </Select>
                <Input aria-label={`Requirement ${i + 1} text`} value={r.text} onChange={(e) => setReq(i, { text: e.target.value })} />
                <IconButton label={`Remove requirement ${i + 1}`} onClick={() => setT({ ...t, requirements: t.requirements.filter((_, j) => j !== i) })}><Trash2 className="size-3.5" /></IconButton>
              </li>
            ))}
          </ul>
          <Button size="sm" className="mt-2" icon={<Plus className="size-3" />} disabled={t.requirements.length >= 100}
            onClick={() => setT({ ...t, requirements: [...t.requirements, { kind: "functional", text: "" }] })}>Add requirement</Button>
        </div>
        {error && <p role="alert" className="text-xs text-danger md:col-span-2">{error}</p>}
      </div>
    </Dialog>
  );
}
