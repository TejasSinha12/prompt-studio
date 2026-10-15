import type { ReqKind, Severity } from "./types";

export const REQ_KIND_LABELS: Record<ReqKind, string> = {
  goal: "Goal",
  functional: "Functional",
  non_functional: "Non-functional",
  security: "Security",
  constraint: "Constraint",
  acceptance: "Acceptance criterion",
  assumption: "Assumption",
  out_of_scope: "Out of scope",
};
export const REQ_KINDS = Object.keys(REQ_KIND_LABELS) as ReqKind[];

export const CATEGORY_LABELS: Record<string, string> = {
  new_application: "New application",
  feature: "Feature",
  bug_fix: "Bug fix",
  refactor: "Refactor",
  code_review: "Code review",
  testing: "Testing",
  documentation: "Documentation",
  data_analysis: "Data analysis",
  writing: "Writing",
  general: "General",
};

export const PROFILE_LABELS: Record<string, string> = {
  claude_code: "Claude Code",
  codex: "OpenAI Codex",
  cursor: "Cursor",
  generic_coding: "Generic coding agent",
  generic_llm: "Generic LLM",
};

export const FINDING_KIND_LABELS: Record<string, string> = {
  confirmed_issue: "Confirmed issue",
  potential_risk: "Potential risk",
  assumption: "Assumption",
  recommendation: "Recommendation",
  unresolved_question: "Unresolved question",
};

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

export function engineLabel(engine: string, model?: string | null): string {
  if (engine === "local_ai") return `Local AI${model ? ` · ${model}` : ""}`;
  if (engine === "manual") return "Manual edit";
  return "Rule-based";
}

export function categoryLabel(c: string): string {
  return CATEGORY_LABELS[c] ?? c.replace(/_/g, " ");
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return formatDate(iso);
}

export function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

export function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "export";
}

export const RUNTIME_LABELS: Record<string, string> = {
  ollama: "Ollama",
  openai_compatible: "OpenAI-compatible local server",
};

export function runtimeLabel(provider: string | undefined): string {
  return RUNTIME_LABELS[provider ?? "ollama"] ?? "Local runtime";
}
