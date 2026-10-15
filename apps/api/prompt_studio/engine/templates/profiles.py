"""Versioned agent export profiles.

Conventions were checked against official documentation on 2026-10-15:
* Claude Code — https://code.claude.com/docs/en/memory
  (./CLAUDE.md or ./.claude/CLAUDE.md; CLAUDE.local.md for personal notes; @path imports;
  .claude/rules/*.md; guidance: keep each CLAUDE.md under ~200 lines; can read AGENTS.md.)
* OpenAI Codex — https://learn.chatgpt.com/docs/agent-configuration/agents-md
  (AGENTS.md discovered from repo root to cwd, AGENTS.override.md takes precedence per
  directory, combined size capped at 32 KiB by default.)
* Cursor — https://cursor.com/docs/context/rules
  (.cursor/rules/*.mdc with frontmatter `description`, `globs`, `alwaysApply`; AGENTS.md
  also supported.)
These conventions change; bump `version` and `verified_on` when re-verifying.
"""

from __future__ import annotations

from pydantic import BaseModel


class InstructionFile(BaseModel):
    path: str
    purpose: str


class AgentProfile(BaseModel):
    id: str
    name: str
    version: str
    verified_on: str
    docs_url: str
    coding: bool
    output_formats: list[str]
    instruction_structure: list[str]
    context_requirements: list[str]
    instruction_files: list[InstructionFile]
    limitations: list[str]
    unsupported: list[str]
    size_guidance: str = ""


PROFILES: dict[str, AgentProfile] = {
    p.id: p
    for p in [
        AgentProfile(
            id="claude_code",
            name="Claude Code",
            version="1.0.0",
            verified_on="2026-10-15",
            docs_url="https://code.claude.com/docs/en/memory",
            coding=True,
            output_formats=["markdown", "claude_md", "plan", "tasks", "tests", "spec"],
            instruction_structure=[
                "Task and objective",
                "Context",
                "Requirements",
                "Constraints",
                "Verification / acceptance",
                "Deliverables",
            ],
            context_requirements=[
                "Repository conventions belong in CLAUDE.md",
                "Task-specific detail belongs in the prompt",
            ],
            instruction_files=[
                InstructionFile(path="CLAUDE.md", purpose="Project instructions shared via source control"),
                InstructionFile(path="CLAUDE.local.md", purpose="Personal, gitignored project preferences"),
                InstructionFile(path=".claude/rules/*.md", purpose="Topic or path-scoped rules"),
            ],
            limitations=[
                "CLAUDE.md is context, not enforced configuration",
                "Long instruction files reduce adherence (docs suggest < 200 lines per file)",
            ],
            unsupported=["Prompt Studio does not run Claude Code or send prompts to it"],
            size_guidance="Keep CLAUDE.md under ~200 lines.",
        ),
        AgentProfile(
            id="codex",
            name="OpenAI Codex",
            version="1.0.0",
            verified_on="2026-10-15",
            docs_url="https://learn.chatgpt.com/docs/agent-configuration/agents-md",
            coding=True,
            output_formats=["markdown", "agents_md", "plan", "tasks", "tests", "spec"],
            instruction_structure=[
                "Objective",
                "Context",
                "Requirements",
                "Constraints",
                "How to verify",
                "Deliverables",
            ],
            context_requirements=["Repository-wide expectations in AGENTS.md", "Task detail in the prompt"],
            instruction_files=[
                InstructionFile(path="AGENTS.md", purpose="Project instructions, discovered from repo root to cwd"),
                InstructionFile(path="AGENTS.override.md", purpose="Per-directory override taking precedence"),
            ],
            limitations=["Combined AGENTS.md content is capped (32 KiB by default)"],
            unsupported=["Prompt Studio does not run Codex or send prompts to it"],
            size_guidance="Keep combined AGENTS.md content under 32 KiB.",
        ),
        AgentProfile(
            id="cursor",
            name="Cursor",
            version="1.0.0",
            verified_on="2026-10-15",
            docs_url="https://cursor.com/docs/context/rules",
            coding=True,
            output_formats=["markdown", "cursor_mdc", "agents_md", "plan", "tasks", "tests", "spec"],
            instruction_structure=["Objective", "Requirements", "Constraints", "Acceptance criteria"],
            context_requirements=["Persistent rules in .cursor/rules/*.mdc", "Task detail in chat prompt"],
            instruction_files=[
                InstructionFile(
                    path=".cursor/rules/<name>.mdc",
                    purpose="Project rule with frontmatter (description, globs, alwaysApply)",
                ),
                InstructionFile(path="AGENTS.md", purpose="Plain Markdown alternative to rules"),
            ],
            limitations=["Plain .md files in .cursor/rules are ignored; use .mdc"],
            unsupported=["Prompt Studio does not run Cursor or send prompts to it"],
        ),
        AgentProfile(
            id="generic_coding",
            name="Generic coding agent",
            version="1.0.0",
            verified_on="2026-10-15",
            docs_url="",
            coding=True,
            output_formats=["markdown", "text", "agents_md", "plan", "tasks", "tests", "spec", "template"],
            instruction_structure=[
                "Role",
                "Objective",
                "Context",
                "Requirements",
                "Constraints",
                "Acceptance criteria",
                "Deliverables",
            ],
            context_requirements=["Paste relevant code or describe the codebase"],
            instruction_files=[
                InstructionFile(path="AGENTS.md", purpose="Widely adopted convention; check your agent")
            ],
            limitations=["Instruction-file support differs between agents; verify for your tool"],
            unsupported=[],
        ),
        AgentProfile(
            id="generic_llm",
            name="Generic LLM workflow",
            version="1.0.0",
            verified_on="2026-10-15",
            docs_url="",
            coding=False,
            output_formats=["markdown", "text", "template", "spec"],
            instruction_structure=["Role", "Task", "Context", "Requirements", "Output format"],
            context_requirements=["Include all needed context in the prompt; chat models have no project files"],
            instruction_files=[],
            limitations=["No repository access is assumed"],
            unsupported=["Instruction files", "Running tests"],
        ),
    ]
}


def get_profile(profile_id: str) -> AgentProfile:
    return PROFILES.get(profile_id) or PROFILES["generic_coding"]
