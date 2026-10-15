"use client";

import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { REQ_KIND_LABELS, REQ_KINDS } from "@/lib/format";
import type { ReqKind, ReqStatus, Requirement } from "@/lib/types";
import { useToast } from "../Toast";
import { Badge, Button, EmptyState, IconButton, Select, Textarea } from "../ui";

const STATUS_TONE: Record<ReqStatus, "ok" | "warn" | "danger" | "neutral"> = {
  confirmed: "ok",
  proposed: "warn",
  unresolved: "warn",
  rejected: "danger",
};

export function RequirementsPanel({ projectId, requirements, onChanged }: { projectId: string; requirements: Requirement[]; onChanged: () => void }) {
  const toast = useToast();
  const [kind, setKind] = useState<ReqKind>("functional");
  const [status, setStatus] = useState<ReqStatus>("confirmed");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [filter, setFilter] = useState<"all" | ReqStatus>("all");

  async function add() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api.post(`/api/projects/${projectId}/requirements`, { kind, text: text.trim(), status });
      setText("");
      onChanged();
    } catch (e) {
      toast(errorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function update(id: string, body: Partial<Pick<Requirement, "kind" | "status" | "text">>) {
    try {
      await api.patch(`/api/requirements/${id}`, body);
      onChanged();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  async function remove(r: Requirement) {
    if (!window.confirm(`Delete this ${REQ_KIND_LABELS[r.kind].toLowerCase()} requirement?\n\n${r.text}`)) return;
    try {
      await api.del(`/api/requirements/${r.id}`);
      onChanged();
    } catch (e) {
      toast(errorMessage(e), "error");
    }
  }

  const shown = requirements.filter((r) => filter === "all" || r.status === filter);
  const grouped = REQ_KINDS.map((k) => [k, shown.filter((r) => r.kind === k)] as const).filter(([, rs]) => rs.length > 0);
  const counts = { confirmed: 0, proposed: 0, unresolved: 0, rejected: 0 } as Record<ReqStatus, number>;
  requirements.forEach((r) => counts[r.status]++);

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-2 rounded-lg border border-border bg-panel-2/50 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <div className="flex flex-wrap gap-2">
          <Select aria-label="Requirement type" value={kind} onChange={(e) => setKind(e.target.value as ReqKind)} className="w-48">
            {REQ_KINDS.map((k) => <option key={k} value={k}>{REQ_KIND_LABELS[k]}</option>)}
          </Select>
          <Select aria-label="Requirement status" value={status} onChange={(e) => setStatus(e.target.value as ReqStatus)} className="w-36">
            <option value="confirmed">Confirmed</option>
            <option value="proposed">Proposed</option>
            <option value="unresolved">Unresolved</option>
          </Select>
        </div>
        <Textarea
          aria-label="New requirement text"
          rows={2}
          placeholder="One requirement per entry, e.g. “Malformed CSV rows are reported with their line number.”"
          value={text}
          maxLength={5000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void add();
            }
          }}
        />
        <div className="flex justify-end">
          <Button type="submit" variant="primary" size="sm" icon={<Plus className="size-3.5" />} busy={busy} disabled={!text.trim()}>
            Add requirement
          </Button>
        </div>
      </form>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted">Show:</span>
        {(["all", "confirmed", "proposed", "unresolved", "rejected"] as const).map((s) => (
          <button key={s} type="button" onClick={() => setFilter(s)} aria-pressed={filter === s}
            className={`rounded px-2 py-0.5 capitalize ${filter === s ? "bg-panel-2 font-medium text-text" : "text-muted hover:text-text"}`}>
            {s}{s !== "all" ? ` (${counts[s]})` : ` (${requirements.length})`}
          </button>
        ))}
      </div>

      {requirements.length === 0 ? (
        <EmptyState title="No requirements yet">
          Add requirements directly, approve recommendations, or answer clarification questions. Only <strong>confirmed</strong> requirements are guaranteed
          to appear in generated prompts; rejected ones never do.
        </EmptyState>
      ) : (
        grouped.map(([k, rs]) => (
          <section key={k} aria-label={REQ_KIND_LABELS[k]}>
            <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">{REQ_KIND_LABELS[k]}</h4>
            <ul className="flex flex-col gap-1.5">
              {rs.map((r) => (
                <li key={r.id} className={`rounded-md border border-border bg-panel px-3 py-2 ${r.status === "rejected" ? "opacity-60" : ""}`}>
                  {editing === r.id ? (
                    <div className="flex flex-col gap-2">
                      <Textarea aria-label="Edit requirement" rows={2} value={editText} onChange={(e) => setEditText(e.target.value)} autoFocus />
                      <div className="flex justify-end gap-1">
                        <Button size="sm" icon={<X className="size-3" />} onClick={() => setEditing(null)}>Cancel</Button>
                        <Button size="sm" variant="primary" icon={<Check className="size-3" />} disabled={!editText.trim()}
                          onClick={() => { void update(r.id, { text: editText.trim() }); setEditing(null); }}>
                          Save
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start gap-2">
                      <p className={`flex-1 text-[13px] ${r.status === "rejected" ? "line-through" : ""}`}>{r.text}</p>
                      <div className="flex shrink-0 items-center gap-1">
                        {r.source !== "user" && <Badge title="Where this requirement came from">{r.source}</Badge>}
                        <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>
                        <Select aria-label="Change status" value={r.status} onChange={(e) => update(r.id, { status: e.target.value as ReqStatus })} className="h-7 w-28 text-xs">
                          <option value="confirmed">Confirm</option>
                          <option value="proposed">Proposed</option>
                          <option value="unresolved">Unresolved</option>
                          <option value="rejected">Reject</option>
                        </Select>
                        <IconButton label="Edit requirement" onClick={() => { setEditing(r.id); setEditText(r.text); }}>
                          <Pencil className="size-3.5" />
                        </IconButton>
                        <IconButton label="Delete requirement" onClick={() => remove(r)} className="hover:text-danger">
                          <Trash2 className="size-3.5" />
                        </IconButton>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
