# Local model validation

Real-model measurements of Prompt Studio's local-AI features. These are
observations from specific runs on one machine, **not benchmarks**: timings
depend on hardware, other load, context size and model version.

Reproduce with (uses a throwaway database; your data is not touched):

```bash
cd apps/api && uv run python scripts/validate_model.py --model qwen3:8b --runs 2
```

The script creates a sample project ("REST API for a team task tracker",
4 confirmed requirements, 1 rejected requirement, deliberately vague wording
such as "fast", "scale well", "latest versions"), runs rule-based analysis,
saves a balanced prompt version, then runs each local-AI operation.

## qwen3:8b — 2026-10-15

- Ollama 0.40.4, macOS 26.6.2, Apple Silicon (arm64), 16 GB RAM
- Model: 8.2B parameters, Q4_K_M, context window 40,960, capabilities: completion, tools, thinking
- Settings: temperature 0.2, `num_ctx` 8192
- Other load during the run: the Playwright E2E suite ran concurrently for part of the time, so timings are pessimistic.

### Thinking off (default), 2 runs

| Run | Operation | Time | Result | Details |
|---|---|---|---|---|
| 1 | analysis | 99.2s | ok | 3 findings, all quoting text that exists in the spec; 4 near-duplicates filtered out |
| 1 | clarify | 15.2s | ok | 5 questions |
| 1 | optimize | 32.7s | ok | 4/4 confirmed requirements preserved verbatim; rejected item not reintroduced |
| 1 | evaluate | 58.0s | ok | feasibility 75 |
| 2 | analysis | 98.8s | ok | 4 findings, evidence verified; 2 near-duplicates filtered out |
| 2 | clarify | 14.4s | ok | 5 questions |
| 2 | optimize | 28.5s | ok | 4/4 preserved; rejected item not reintroduced |
| 2 | evaluate | 67.1s | ok | feasibility 75 |

### Thinking on, 1 run

| Run | Operation | Time | Result | Details |
|---|---|---|---|---|
| 1 | analysis | 124.3s | ok | 4 findings, evidence verified; 1 already reported by rules and 1 over the category cap filtered out |
| 1 | clarify | 93.0s | ok | 5 questions |
| 1 | optimize | 104.3s | ok | 4/4 preserved; rejected item not reintroduced |
| 1 | evaluate | 76.9s | ok | feasibility 75 |

No run needed the one-shot schema repair; all structured output validated on
the first attempt.

## What the model actually produced

**Analysis.** Findings were relevant to the stated features and quoted
distinct phrases, e.g. "What is the definition of 'teammate'?" (quoting
"assign them to teammates") and "What constitutes a 'task'?". Weaknesses
observed:

- **Severity inflation:** definitional gaps were rated *high*; *medium* would
  be more accurate.
- **Misses:** the unspecified sign-in method ("Users sign in") was not
  reported in the runs inspected.
- Thinking mode filtered differently but did not clearly improve findings,
  while making clarify and optimize roughly 3–6× slower.

**Feasibility.** 75 in every run for a deliberately vague spec. That is
plausible under the rubric ("minor gaps"), though arguably generous.

**Optimize.** Kept every confirmed requirement verbatim and did not
reintroduce the rejected one. It also roughly halved the prompt length by
dropping template guidance sections. Review the diff before saving.

## Prompt-engineering changes driven by these runs

The first real run, before these changes, returned 15 findings. All were
"missing feature X" items quoting the same sentence, several were
near-duplicates, and one re-proposed a requirement the user had **rejected**.
Changes made in response:

1. The analysis prompt now includes the user's rejected items and the
   findings rules already reported. It asks only for gaps in features the
   user *did* mention and forbids suggesting new features.
2. Model output is post-filtered deterministically: near-duplicates, matches
   to rejected items, findings already reported by rules, and anything over
   3 per category are dropped. Drop counts are returned in the job result.
3. An intermediate prompt that said "return an empty list if there are no
   real problems" made the model return nothing (0.5 s). The prompt now asks
   for 3–10 findings unless the specification is genuinely complete.
4. The feasibility schema now asks for concerns before the score, with
   explicit score bands. Before this change the model scored the same vague
   spec 95.

## Recommendation

`qwen3:8b` with thinking **off** is a usable default on a 16 GB Apple Silicon
Mac. Treat its analysis as a second opinion next to the rule-based checks,
and expect 1–2 minutes per analysis. `qwen3:4b` should be faster but has not
been validated; run the script above to check it.
