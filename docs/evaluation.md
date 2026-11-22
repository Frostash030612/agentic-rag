# Evaluation

The harness is deliberately **deterministic and cheap**: answer checks are keyword
based, trajectory checks are structural, and no LLM judge is used. This makes CI and
regression runs reproducible; it also means the numbers are a screening signal, not a
claim of semantic correctness.

## Task set

26 tasks in `data/tasks.jsonl`:

| Category | Count | Example | What it tests |
| --- | --- | --- | --- |
| Single-hop KB | 15 | ALM-1042 trigger/steps | retrieval + generation |
| Ticket lookup | 4 | T-1001 status; T-9999 missing | tool selection, no fabrication |
| Calculator | 3 | 24 wafers × 92.5% | tool use, numeric answer |
| Mixed multi-step | 2 | ticket + KB; ticket + calculator | orchestration |
| Refusal | 2 | EUV wavelength; company capacity | answerable=false |

Each task may define:

- `must_include` — exact substrings that must appear;
- `must_include_any` — alternatives, e.g. `["成本", "费用", "价格"]`;
- `must_not_include` — hallucination traps;
- `expected_tools` / `forbidden_tools` — trajectory checks;
- `max_steps` — per-task budget.

## Metrics

- **Answer accuracy**: all required substrings present, no forbidden substrings.
- **Tool selection**: expected tools are a subset of called tools, and no forbidden
  tool was called.
- **Task success**: answer correct **and** tools correct.
- **pass^k**: run the task k times; all k runs must succeed.
- **Avg steps / avg latency / P95**: cost of multi-step execution.
- **Refusal**: unanswerable task must return `answerable=false`.

Run:

```bash
python -m agentic_rag eval --mode both --runs 1
```

Artifacts:

- `eval/report.json` — machine-readable, includes per-run answers and tool calls;
- `eval/rag_report.md`, `eval/agent_report.md` — human-readable;
- `eval/comparison.md` — RAG-only vs Agent;
- `runs/<mode>/<task>/run-<n>.json` — step-level traces.

## Reference result

Qwen3-8B, 26 tasks, `runs=1`, reference run 2026-11-14:

| Mode | Task success | Answer | Tool selection | Avg steps | Avg latency | P95 |
| --- | --- | --- | --- | --- | --- | --- |
| RAG-only | **18/26 = 69.2%** | 69.2% | — | 1.00 | **3.06s** | **5.72s** |
| Agent | **24/26 = 92.3%** | 92.3% | **100%** | 2.15 | 7.78s | 12.43s |
| Delta | **+23.1pp** | +23.1pp | — | +1.15 | +4.72s | +6.71s |

`pass^3` on a representative 8-task subset:

| Metric | Value |
| --- | --- |
| pass^3 | **6/8 = 75%** |
| Manual review after one keyword false negative | **7/8 = 87.5%** |

## Where the gain comes from

RAG-only failed 8 tasks:

| Failed tasks | Why |
| --- | --- |
| KB03 query rewriting | one retrieval cannot rewrite/HyDE |
| TK01–TK04 tickets | no `lookup_ticket`; model can only guess/refuse |
| CA01 calculator | no `calculator`; mental arithmetic is unreliable |
| MX01 / MX02 mixed | requires ticket + KB/calculator |

The Agent fixed **7 of 8**. That is the point of tool orchestration: not “a smarter
model”, but a channel to fetch facts and execute deterministic operations.

## Failure analysis

### CA01 — format fragility

- Task: `24 × 92.5% = ?`
- Trace: `calculator(24*0.925) -> 22.2`, then the model emitted invalid JSON twice
  and hit `max_steps`.
- Result: 3/3 runs failed with `达到最大步数，未能完成。`
- Root cause: JSON action protocol is strict; after a successful calculation the model
  sometimes “relaxes” into prose.
- Fixes: native JSON mode / structured output; one targeted repair pass; a final-answer
  fallback built from the last observation; report format-failure rate separately.

### KB05 — deterministic judge false negative

- Task: “长上下文窗口越来越大，是不是就不需要 RAG 了？”
- Answer: “互补而非替代；控制上下文、提高有效利用率、减少 Lost in the Middle.”
- The checker required “成本/费用/价格”; the answer was correct but phrased differently.
- Manual review passes it. This is why the README reports both the automatic score and
  the manually reviewed score.

### Why not an LLM judge here?

The companion RAG project already learned this lesson: an LLM judge needs calibration
and still has a lenient bias (κ≈0.52 on 49 human labels). For this repo, deterministic
checks are the guardrail; an LLM judge is a roadmap item, not a hidden dependency in CI.

## Caveats

- 26 tasks is small; use this for relative comparison, not a production accuracy claim.
- The tasks are authored for this demo and may align with the prompt/tools.
- Qwen3-8B is nondeterministic even at temperature 0; pass^k is the honest view.
- The reference run is one sample; rerun `make eval` to reproduce.
- The mock tickets and illustrative DRAM docs are not a production corpus.
