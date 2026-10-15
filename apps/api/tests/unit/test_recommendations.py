from prompt_studio.engine.analyzer.rules import analyze
from prompt_studio.engine.recommendations.generator import needs_edit, recommend
from tests.unit.test_analyzer import spec


def test_significant_findings_get_recommendations_with_all_fields():
    findings = analyze(spec("Build a fast login service", task_category="feature"))
    recs = [recommend(f) for f in findings]
    recs = [r for r in recs if r]
    assert recs
    for r in recs:
        assert r.problem and r.rationale and r.proposal and r.benefits and r.tradeoffs and r.complexity
        assert r.verification and r.requirement_kind and r.requirement_text


def test_info_and_questions_have_no_recommendation():
    findings = analyze(spec("Database TBD", [("assumption", "x y z", "proposed")]))
    for f in findings:
        if f.severity == "info" or f.kind == "unresolved_question":
            assert recommend(f) is None


def test_placeholder_detection():
    assert needs_edit("Performance target: [state latency]")
    assert not needs_edit("Read list[str] values")  # short brackets are not placeholders
    assert not needs_edit("All tests pass")
