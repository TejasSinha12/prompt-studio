from prompt_studio.engine.analyzer.rules import analyze
from prompt_studio.engine.spec import ProjectSpec, PromptConfig, SpecRequirement


def spec(idea="", reqs=(), **cfg):
    return ProjectSpec(
        name="T",
        idea=idea,
        config=PromptConfig(**cfg),
        requirements=[SpecRequirement(id=f"r{i}", kind=k, text=t, status=s) for i, (k, t, s) in enumerate(reqs)],
    )


def rule_ids(findings):
    return {f.rule_id for f in findings}


def by_rule(findings, rid):
    return [f for f in findings if f.rule_id == rid]


def test_short_idea_flagged_high():
    f = analyze(spec("make an app"))
    hit = by_rule(f, "REQ-001")
    assert hit and hit[0].severity == "high" and hit[0].kind == "confirmed_issue"


def test_missing_acceptance_criteria_detected_and_resolved():
    s = spec(
        "Build a command line tool that converts CSV files into JSON documents for analysts", task_category="feature"
    )
    assert "ACC-001" in rule_ids(analyze(s))
    s.requirements.append(SpecRequirement(id="a", kind="acceptance", text="Converts sample.csv correctly"))
    assert "ACC-001" not in rule_ids(analyze(s))


def test_acceptance_phrase_in_idea_counts():
    s = spec("Build a converter. Done when all sample files convert without errors and tests pass.")
    assert "ACC-001" not in rule_ids(analyze(s))


def test_missing_tests_only_for_coding_tasks():
    assert "TST-001" in rule_ids(analyze(spec("Build a thing that converts files for people", task_category="feature")))
    assert "TST-001" not in rule_ids(analyze(spec("Write a blog post about converting files", task_category="writing")))


def test_security_severity_depends_on_sensitive_evidence():
    f = by_rule(analyze(spec("Add a login page with password reset for users", task_category="feature")), "SEC-001")
    assert f[0].severity == "high" and f[0].evidence[0].quote
    f2 = by_rule(analyze(spec("Add a colour picker widget to the toolbar", task_category="feature")), "SEC-001")
    assert f2[0].severity == "low"


def test_ambiguous_terms_with_evidence_and_quantified_skip():
    f = by_rule(analyze(spec("The app must be fast and user-friendly, etc.")), "AMB-001")
    terms = {x.title for x in f}
    assert 'Ambiguous term: "fast"' in terms and 'Ambiguous term: "user-friendly"' in terms
    assert all(x.evidence and x.evidence[0].source == "idea" for x in f)
    f2 = by_rule(analyze(spec("Responses must be fast (under 200 ms p95).")), "AMB-001")
    assert not any('"fast"' in x.title for x in f2)


def test_duplicate_and_contradiction():
    s = spec(
        "x",
        [
            ("functional", "Users can export reports as PDF", "confirmed"),
            ("functional", "Users can export reports as PDF.", "confirmed"),
            ("constraint", "The app must store data in the cloud", "confirmed"),
            ("constraint", "The app must not store data in the cloud", "confirmed"),
        ],
    )
    f = analyze(s)
    assert by_rule(f, "DUP-001")[0].kind == "confirmed_issue"
    con = by_rule(f, "CON-001")
    assert con and con[0].kind == "potential_risk" and len(con[0].evidence) == 2


def test_rejected_requirements_ignored():
    s = spec(
        "x",
        [
            ("functional", "Users can export reports as PDF", "confirmed"),
            ("functional", "Users can export reports as PDF", "rejected"),
        ],
    )
    assert not by_rule(analyze(s), "DUP-001")


def test_keyword_contradiction_offline_vs_cloud():
    f = by_rule(analyze(spec("It must work offline. It will call the OpenAI API for summaries.")), "CON-002")
    assert f and f[0].confidence == "low"


def test_performance_risk_cleared_by_numeric_nfr():
    s = spec("A real-time dashboard for sensor data")
    assert "PRF-001" in rule_ids(analyze(s))
    s.requirements.append(SpecRequirement(id="n", kind="non_functional", text="Updates render within 500 ms"))
    assert "PRF-001" not in rule_ids(analyze(s))


def test_complexity_for_small_project():
    f = by_rule(analyze(spec("A todo list using microservices and kubernetes", project_size="small")), "CPX-001")
    assert f and f[0].severity == "medium"
    assert not by_rule(analyze(spec("A todo list using microservices", project_size="large")), "CPX-001")


def test_unresolved_markers_and_assumptions():
    s = spec("Database choice TBD", [("assumption", "Users have modern browsers", "proposed")])
    ids = rule_ids(analyze(s))
    assert "UNR-001" in ids and "UNR-002" in ids


def test_fingerprints_stable_and_unique():
    s = spec("The app must be fast and simple, etc", task_category="feature")
    a, b = analyze(s), analyze(s)
    assert [x.fingerprint for x in a] == [x.fingerprint for x in b]
    assert len({x.fingerprint for x in a}) == len(a)


def test_all_findings_have_required_fields():
    for f in analyze(
        spec("Build a fast real-time login system with microservices, TBD", task_category="new_application")
    ):
        assert f.title and f.explanation and f.evidence and f.impact and f.solution and f.verification
        assert f.severity in {"critical", "high", "medium", "low", "info"}
