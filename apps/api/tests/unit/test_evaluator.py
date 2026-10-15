from prompt_studio.engine.evaluator.quality import evaluate
from prompt_studio.engine.optimizer.builder import build_prompt
from tests.unit.test_builder import make


def dim(r, i):
    return next(d for d in r.dimensions if d.id == i)


def test_vague_prompt_scores_lower_than_structured():
    weak = evaluate("Make a fast, user-friendly, modern app etc.")
    strong = evaluate(build_prompt(make(testing="Pytest unit tests"), "detailed").content)
    assert weak.score < strong.score
    assert dim(weak, "clarity").findings and dim(weak, "clarity").findings[0].evidence


def test_feasibility_requires_ai_and_excluded_from_score():
    r = evaluate("Do a thing.")
    f = dim(r, "feasibility")
    assert f.score is None and f.method == "requires_local_ai"


def test_redundancy_detected():
    t = "Users must be able to export the report as PDF.\nUsers must be able to export the report as PDF.\n"
    assert dim(evaluate(t), "redundancy").findings


def test_contradiction_detected():
    t = "- The service must log every request body\n- The service must not log every request body\n"
    assert dim(evaluate(t), "consistency").score < 100


def test_token_estimate_labelled():
    r = evaluate("hello world " * 10)
    assert "estimate" in dim(r, "efficiency").summary
    assert r.metrics["token_estimate"] > 0


def test_non_coding_security_not_applicable():
    assert dim(evaluate("Write a poem", coding=False), "security").method == "not_applicable"
