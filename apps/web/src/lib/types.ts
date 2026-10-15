// Mirrors apps/api/prompt_studio/schemas.py. Keep in sync when the API changes.

export type ReqKind =
  | "goal"
  | "functional"
  | "non_functional"
  | "security"
  | "constraint"
  | "acceptance"
  | "assumption"
  | "out_of_scope";
export type ReqStatus = "confirmed" | "proposed" | "rejected" | "unresolved";
export type Variant = "concise" | "balanced" | "detailed";
export type ProfileId = "claude_code" | "codex" | "cursor" | "generic_coding" | "generic_llm";
export type Engine = "rule_based" | "local_ai";

export interface Tag {
  id: string;
  name: string;
}

export interface PromptConfig {
  target_agent: string;
  task_category: string;
  language: string;
  framework: string;
  existing_codebase: string;
  project_size: "" | "small" | "medium" | "large";
  detail_level: "" | "concise" | "balanced" | "detailed";
  tone: string;
  output_format: string;
  testing: string;
  security: string;
  performance: string;
  hardware: string;
  budget: string;
  architecture: string;
  restrictions: string;
}

export interface Requirement {
  id: string;
  kind: ReqKind;
  text: string;
  status: ReqStatus;
  source: string;
  recommendation_id: string | null;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  archived: boolean;
  revision: number;
  tags: Tag[];
  created_at: string;
  updated_at: string;
  task_category: string;
  open_findings: number;
  proposed_recommendations: number;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  original_idea: string;
  tech_stack: string;
  config: PromptConfig;
  archived: boolean;
  revision: number;
  tags: Tag[];
  requirements: Requirement[];
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
}

export interface ProjectEvent {
  id: string;
  kind: string;
  summary: string;
  created_at: string;
}

export interface Evidence {
  source: string;
  quote: string;
  line: number | null;
}

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Finding {
  id: string;
  fingerprint: string;
  engine: Engine;
  model: string | null;
  rule_id: string;
  category: string;
  kind: string;
  title: string;
  explanation: string;
  evidence: Evidence[];
  severity: Severity;
  confidence: "high" | "medium" | "low";
  impact: string;
  solution: string;
  alternative: string;
  verification: string;
  status: "open" | "acknowledged" | "dismissed" | "resolved";
  created_at: string;
  updated_at: string;
}

export interface AnalysisRun {
  id: string;
  engine: Engine;
  model: string | null;
  status: string;
  finding_count: number;
  duration_ms: number;
  error: string | null;
  created_at: string;
}

export interface AnalysisOut {
  run: AnalysisRun;
  findings: Finding[];
  new_findings: number;
  resolved_findings: number;
  new_recommendations: number;
}

export interface Alternative {
  title: string;
  requirement_text: string;
  tradeoffs: string;
}

export interface RecommendationEvent {
  id: string;
  from_status: string | null;
  to_status: string;
  note: string;
  created_at: string;
}

export type RecStatus = "proposed" | "approved" | "rejected" | "deferred";

export interface Recommendation {
  id: string;
  finding_id: string | null;
  fingerprint: string;
  engine: Engine;
  model: string | null;
  title: string;
  problem: string;
  rationale: string;
  proposal: string;
  benefits: string;
  tradeoffs: string;
  complexity: string;
  dependencies: string;
  disadvantages: string;
  verification: string;
  requirement_kind: ReqKind;
  requirement_text: string;
  alternatives: Alternative[];
  status: RecStatus;
  needs_edit: boolean;
  events: RecommendationEvent[];
  created_at: string;
  updated_at: string;
}

export interface ClarificationQuestion {
  id: string;
  question: string;
  why: string;
  suggested_kind: ReqKind;
  source: Engine;
  finding_id: string | null;
}

export interface Section {
  id: string;
  title: string;
  source: "user" | "template" | "mixed";
}

export interface PreservationItem {
  requirement_id: string;
  kind: string;
  text: string;
  preserved: boolean;
  coverage: number;
}

export interface BuildResult {
  variant: Variant;
  profile_id: string;
  profile_version: string;
  content: string;
  sections: Section[];
  preservation: PreservationItem[];
  warnings: string[];
  char_count: number;
  word_count: number;
  token_estimate: number;
  generator: string;
}

export interface Version {
  id: string;
  prompt_id: string;
  number: number;
  content: string;
  variant: string;
  profile_id: string;
  profile_version: string;
  generator: "rule_based" | "local_ai" | "manual";
  model: string | null;
  source_snapshot: Record<string, unknown>;
  change_summary: string;
  parent_version_id: string | null;
  created_at: string;
}

export type VersionMeta = Omit<Version, "content" | "prompt_id" | "profile_version" | "source_snapshot">;

export interface PromptSummary {
  id: string;
  project_id: string | null;
  project_name: string | null;
  title: string;
  category: string;
  target_agent: string;
  favorite: boolean;
  archived: boolean;
  tags: Tag[];
  current_version_id: string | null;
  version_count: number;
  created_at: string;
  updated_at: string;
}

export interface PromptDetail extends PromptSummary {
  current_version: Version | null;
  versions: VersionMeta[];
}

export interface EvalFinding {
  message: string;
  evidence: string[];
  fix: string;
}

export interface Dimension {
  id: string;
  name: string;
  score: number | null;
  method: "rule_based" | "local_ai" | "requires_local_ai" | "not_applicable";
  summary: string;
  findings: EvalFinding[];
}

export interface Evaluation {
  id: string | null;
  prompt_version_id: string | null;
  engine: Engine;
  model: string | null;
  score: number | null;
  formula: string;
  dimensions: Dimension[];
  metrics: Record<string, number>;
  created_at: string | null;
  prompt_id: string | null;
  prompt_title: string | null;
  version_number: number | null;
}

export interface ExportFile {
  format: string;
  filename: string;
  media_type: string;
  content: string;
}

export interface ExportFormat {
  id: string;
  label: string;
  filename: string;
}

export interface AppSettings {
  ollama_url: string;
  allow_remote_ollama: boolean;
  model: string | null;
  timeout_seconds: number;
  max_retries: number;
  num_ctx: number;
  temperature: number;
  max_concurrent_jobs: number;
  default_target_agent: ProfileId;
}

export interface ModelInfo {
  name: string;
  size_bytes: number | null;
  parameter_size: string | null;
  quantization: string | null;
  family: string | null;
  modified_at: string | null;
}

export interface ModelDetails {
  name: string;
  context_length: number | null;
  capabilities: string[];
  parameter_size: string | null;
  quantization: string | null;
  family: string | null;
}

export interface ModelsStatus {
  available: boolean;
  endpoint: string;
  version: string | null;
  error: string | null;
  error_code: string | null;
  selected_model: string | null;
  selected_model_installed: boolean;
  models: ModelInfo[];
}

export type JobKind = "analysis" | "optimize" | "clarify" | "evaluate";

export interface Job {
  id: string;
  kind: JobKind;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  project_id: string | null;
  version_id: string | null;
  model: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  error_code: string | null;
  result: Record<string, unknown> | null;
}

export interface OptimizeResult {
  content: string;
  base_content: string;
  preservation: PreservationItem[];
  warnings: string[];
  rejected_reintroduced: string[];
  model: string;
  engine: "local_ai";
  variant: Variant;
}

export interface Backup {
  name: string;
  size_bytes: number;
  created_at: string;
}

export interface BackupValidation {
  name: string;
  valid: boolean;
  checks: { name: string; ok: boolean; detail: string }[];
}

export interface TaskTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  idea: string;
  config: Record<string, string>;
  requirements: { kind: ReqKind; text: string }[];
}

export interface AgentProfile {
  id: ProfileId;
  name: string;
  version: string;
  verified_on: string;
  docs_url: string;
  coding: boolean;
  output_formats: string[];
  instruction_structure: string[];
  context_requirements: string[];
  instruction_files: { path: string; purpose: string }[];
  limitations: string[];
  unsupported: string[];
  size_guidance: string;
}

export interface SystemInfo {
  data_dir: string;
  database: string;
  backups_dir: string;
  total_memory_bytes: number | null;
  api_token_enabled: boolean;
  version: string;
}

export interface Dashboard {
  counts: { projects: number; archived_projects: number; prompts: number; versions: number };
  recent_projects: ProjectSummary[];
  needs_review: { project_id: string; project_name: string; proposed_recommendations: number }[];
  recent_versions: {
    id: string;
    prompt_id: string;
    prompt_title: string;
    number: number;
    variant: string;
    generator: string;
    created_at: string;
  }[];
  recent_findings: {
    id: string;
    project_id: string;
    project_name: string;
    title: string;
    severity: Severity;
    engine: Engine;
    kind: string;
  }[];
}
