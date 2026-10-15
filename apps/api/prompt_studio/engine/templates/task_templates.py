"""Built-in task templates. Creating a project from a template pre-fills
configuration and a skeleton idea; every pre-filled requirement is created
with status `proposed`, so nothing enters the confirmed spec without review.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateRequirement(BaseModel):
    kind: str
    text: str


class TaskTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str
    idea: str
    config: dict[str, str] = Field(default_factory=dict)
    requirements: list[TemplateRequirement] = Field(default_factory=list)


TEMPLATES: list[TaskTemplate] = [
    TaskTemplate(
        id="new-web-app",
        name="New web application",
        category="new_application",
        description="Greenfield application with a UI and persistence.",
        idea="Build a web application that lets [who] do [what] so that [why].\n\nCore features:\n- \n- \n",
        config={"task_category": "new_application", "detail_level": "detailed", "project_size": "medium"},
        requirements=[
            TemplateRequirement(
                kind="acceptance", text="The main user workflow works end to end and is covered by an automated test."
            ),
            TemplateRequirement(
                kind="non_functional", text="The UI is keyboard accessible and meets WCAG 2.2 AA contrast."
            ),
            TemplateRequirement(kind="security", text="All user input is validated on the server."),
        ],
    ),
    TaskTemplate(
        id="feature",
        name="Add a feature",
        category="feature",
        description="Add a feature to an existing codebase.",
        idea="Add [feature] to the existing [application]. Users should be able to [behaviour].",
        config={"task_category": "feature", "detail_level": "balanced"},
        requirements=[
            TemplateRequirement(kind="constraint", text="Follow the existing code conventions and architecture."),
            TemplateRequirement(
                kind="acceptance", text="New behaviour is covered by tests and the existing test suite still passes."
            ),
        ],
    ),
    TaskTemplate(
        id="bug-fix",
        name="Fix a bug",
        category="bug_fix",
        description="Reproduce, fix and regression-test a defect.",
        idea="Fix the bug where [observed behaviour] instead of [expected behaviour].\n\nSteps to reproduce:\n1. \n",
        config={"task_category": "bug_fix", "detail_level": "concise", "project_size": "small"},
        requirements=[
            TemplateRequirement(
                kind="acceptance", text="A regression test reproduces the bug and passes after the fix."
            ),
            TemplateRequirement(kind="out_of_scope", text="Do not refactor unrelated code."),
        ],
    ),
    TaskTemplate(
        id="refactor",
        name="Refactor",
        category="refactor",
        description="Improve structure without changing behaviour.",
        idea="Refactor [module] to [goal] without changing external behaviour.",
        config={"task_category": "refactor", "detail_level": "balanced"},
        requirements=[
            TemplateRequirement(kind="constraint", text="External behaviour and public interfaces must not change."),
            TemplateRequirement(kind="acceptance", text="All existing tests pass without modification."),
        ],
    ),
    TaskTemplate(
        id="code-review",
        name="Code review",
        category="code_review",
        description="Review a change for correctness, security and maintainability.",
        idea="Review the changes in [branch/PR/files] for correctness, security and maintainability.",
        config={
            "task_category": "code_review",
            "detail_level": "balanced",
            "output_format": "List of findings with file:line, severity and suggested fix",
        },
        requirements=[
            TemplateRequirement(
                kind="constraint", text="Only report issues with concrete evidence; do not modify code."
            ),
        ],
    ),
    TaskTemplate(
        id="write-tests",
        name="Write tests",
        category="testing",
        description="Add tests for existing code.",
        idea="Add tests for [module/function] covering normal cases, edge cases and error handling.",
        config={"task_category": "testing", "detail_level": "balanced"},
        requirements=[
            TemplateRequirement(
                kind="constraint", text="Do not change production code unless a bug is found; report bugs separately."
            ),
        ],
    ),
    TaskTemplate(
        id="documentation",
        name="Documentation",
        category="documentation",
        description="Write or update technical documentation.",
        idea="Write documentation for [component] aimed at [audience].",
        config={"task_category": "documentation", "target_agent": "generic_llm", "detail_level": "balanced"},
    ),
    TaskTemplate(
        id="general-llm",
        name="General LLM task",
        category="general",
        description="Non-coding prompt for a chat model.",
        idea="I need help with [task]. Context: [context].",
        config={"task_category": "general", "target_agent": "generic_llm", "detail_level": "concise"},
    ),
]

TEMPLATES_BY_ID = {t.id: t for t in TEMPLATES}
