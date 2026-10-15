import { PageHeader } from "@/components/ui";

const SECTIONS: { id: string; title: string; body: React.ReactNode }[] = [
  {
    id: "workflow",
    title: "Workflow",
    body: (
      <ol className="list-decimal space-y-1 pl-5">
        <li>Create a project (blank or from a template) and describe your rough idea. Partial input is fine.</li>
        <li>Optionally fill in the prompt configuration (target agent, category, stack, constraints…). Save with Ctrl/Cmd+S.</li>
        <li>Run <strong>rule-based analysis</strong> in the Findings panel. It works offline and is deterministic.</li>
        <li>Review <strong>recommendations</strong>: approve (optionally editing the text or choosing an alternative), reject, or defer. Only approved items change the confirmed specification.</li>
        <li>Answer <strong>clarification</strong> questions; each answer becomes a confirmed requirement.</li>
        <li>Open the <strong>Prompt</strong> tab to compare the concise, balanced and detailed variants side by side. Edit manually or refine with local AI.</li>
        <li><strong>Save</strong> a version. Versions are immutable; restoring an old version creates a new one.</li>
        <li><strong>Export</strong> as Markdown, plain text, CLAUDE.md, AGENTS.md, Cursor .mdc, plan, tasks, tests, spec, template — or all agent files as a ZIP.</li>
      </ol>
    ),
  },
  {
    id: "labels",
    title: "Rule-based vs. local AI",
    body: (
      <>
        <p>Every finding, recommendation, prompt version and evaluation is labelled with the engine that produced it:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li><strong>Rule-based</strong> — deterministic checks implemented in Prompt Studio. Same input, same output. No network.</li>
          <li><strong>Local AI · model</strong> — produced by the model you selected in Ollama, only when you click a local-AI action. Output is validated against a schema; invalid output is repaired at most once, otherwise the action fails and nothing is stored. Evidence quotes that do not appear in your text lower the confidence to “low”.</li>
          <li><strong>Manual</strong> — your own edits.</li>
        </ul>
        <p>Prompt Studio never presents rule-based output as AI output and never falls back to a cloud provider.</p>
      </>
    ),
  },
  {
    id: "findings",
    title: "Findings and severity",
    body: (
      <>
        <p>Findings are classified as <em>confirmed issue</em> (objectively observable, e.g. no acceptance criteria), <em>potential risk</em> (heuristic indicator, e.g. keyword-based contradiction), <em>assumption</em>, or <em>unresolved question</em>. Each includes evidence, severity, confidence, impact, proposed solution and a verification method.</p>
        <p>Findings keep a stable ID across runs. Dismissed findings stay dismissed; findings whose cause disappears are marked resolved. Contradiction detection is heuristic and incomplete.</p>
      </>
    ),
  },
  {
    id: "variants",
    title: "Prompt variants and preservation",
    body: (
      <>
        <p>The builder renders your text verbatim, omits empty sections, and only adds generic guidance (labelled <em>template</em>) to balanced/detailed variants of coding tasks. Rejected requirements are never rendered. Unconfirmed assumptions are labelled as such.</p>
        <p>The <strong>preservation report</strong> checks that every confirmed requirement appears verbatim in the output — for generated variants, local-AI refinements and manual edits.</p>
      </>
    ),
  },
  {
    id: "scores",
    title: "Quality score formula",
    body: (
      <>
        <p>Rule-based dimensions (clarity, completeness, consistency, context, constraints, acceptance criteria, testability, security coverage, redundancy, token efficiency) each produce a 0–100 sub-score with the evidence used. The aggregate is the <strong>unweighted mean of the rule-based dimensions</strong>. Implementation feasibility is judgment-based and only assessed by local AI, reported separately.</p>
        <p>The score is a heuristic for the presence of good-practice signals. It is not a probability of success and not a measure of the resulting code’s quality. Token counts are estimates (max of characters/4 and words×1.3), not tokenizer output.</p>
      </>
    ),
  },
  {
    id: "privacy",
    title: "Privacy and security",
    body: (
      <ul className="list-disc space-y-1 pl-5">
        <li>All data is stored in a local SQLite database (see Settings for the path). No telemetry; no cloud providers.</li>
        <li>The API and UI bind to 127.0.0.1. Requests with non-loopback Host headers are rejected (DNS-rebinding defence); mutating requests require a custom header and an allowed Origin (CSRF defence).</li>
        <li>Set <code>PROMPT_STUDIO_API_TOKEN</code> to require a token for API access from other local processes. The UI proxy adds it server-side.</li>
        <li>Markdown is rendered without raw HTML and sanitized; images are not loaded.</li>
        <li>Localhost is not a complete security boundary: other software running as your user can read the database file. It is not encrypted at rest.</li>
      </ul>
    ),
  },
  {
    id: "backups",
    title: "Backups and recovery",
    body: (
      <p>Create backups in Settings. Restore validates integrity, schema version and foreign keys first, and takes a safety backup of the current data. “Delete all data” also takes a safety backup. Backups live in the data directory’s <code>backups/</code> folder; copy them elsewhere for off-machine safety.</p>
    ),
  },
  {
    id: "limitations",
    title: "Known limitations",
    body: (
      <ul className="list-disc space-y-1 pl-5">
        <li>Rule-based analysis uses keyword and structure heuristics; it can miss issues and produce false positives.</li>
        <li>Local-AI jobs are held in memory and are cancelled when the backend restarts.</li>
        <li>Local codebase context (reading a project directory) is not implemented yet.</li>
        <li>Agent instruction-file conventions were verified on 2026-10-15 and may change.</li>
        <li>Single-user application: no accounts, no sync, no multi-user editing (stale edits from a second tab are detected and rejected).</li>
      </ul>
    ),
  },
];

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-6">
      <PageHeader title="Documentation" description="How Prompt Studio works, what it stores, and what it does not claim." />
      <nav aria-label="On this page" className="mb-6 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {SECTIONS.map((s) => <a key={s.id} href={`#${s.id}`} className="text-accent hover:underline">{s.title}</a>)}
      </nav>
      <div className="flex flex-col gap-6 text-[13px] leading-relaxed">
        {SECTIONS.map((s) => (
          <section key={s.id} id={s.id} aria-labelledby={`${s.id}-h`} className="flex scroll-mt-4 flex-col gap-2">
            <h2 id={`${s.id}-h`} className="text-base font-semibold">{s.title}</h2>
            {s.body}
          </section>
        ))}
      </div>
    </div>
  );
}
