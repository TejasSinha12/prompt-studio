from prompt_studio.engine.optimizer.builder import build_all, build_prompt, check_preservation
from prompt_studio.engine.spec import ProjectSpec, PromptConfig, SpecRequirement


def make(**cfg):
    return ProjectSpec(
        name="Converter",
        idea="Build a CLI that converts CSV to JSON.",
        config=PromptConfig(task_category="feature", **cfg),
        requirements=[
            SpecRequirement(id="1", kind="functional", text="Read CSV from a file path argument"),
            SpecRequirement(id="2", kind="acceptance", text="Converting sample.csv produces sample.json"),
            SpecRequirement(id="3", kind="security", text="Reject paths outside the working directory"),
            SpecRequirement(id="4", kind="functional", text="Stream rows to support huge files", status="rejected"),
            SpecRequirement(id="5", kind="assumption", text="Input is UTF-8", status="proposed"),
            SpecRequirement(id="6", kind="non_functional", text="Handles 1 GB files with < 200 MB memory"),
        ],
    )


def test_all_variants_preserve_confirmed_requirements():
    for r in build_all(make()):
        assert all(p.preserved for p in r.preservation), r.variant
        assert "Stream rows" not in r.content  # rejected never rendered
        assert "Unconfirmed assumption" in r.content and "Input is UTF-8" in r.content


def test_concise_is_shorter_than_detailed_and_template_sections_labelled():
    c, b, d = build_all(make())
    assert c.char_count < b.char_count < d.char_count
    assert all(s.source != "template" for s in c.sections)
    assert any(s.source == "template" for s in d.sections)


def test_empty_sections_omitted_for_minimal_input():
    r = build_prompt(
        ProjectSpec(
            name="x",
            idea="Summarise this article",
            config=PromptConfig(task_category="general", target_agent="generic_llm"),
        ),
        "balanced",
    )
    titles = [s.title for s in r.sections]
    assert titles == ["Role and objective"]
    assert r.word_count < 40


def test_original_idea_verbatim():
    r = build_prompt(make(), "concise")
    assert "Build a CLI that converts CSV to JSON." in r.content


def test_preservation_detects_missing():
    p = check_preservation("nothing here", make())
    assert not any(x.preserved for x in p)
    assert all(0 <= x.coverage < 1 for x in p)
