# 90-second demo script

Goal: show **tool orchestration + trace + failure awareness**, not just a chat box.

## Setup

```bash
cd AgenticRAG
python -m agentic_rag demo          # replay, no API key
# or, for live model calls:
python -m agentic_rag demo --live
```

The replay mode uses three committed traces:

- `mx01_ticket_and_kb.json` — ticket → KB → final;
- `tk01_ticket.json` — single tool call;
- `ca01_format_failure.json` — calculator succeeds, then invalid JSON → max_steps.

## Script

| Time | Action | What you say |
| --- | --- | --- |
| 0:00 | `python -m agentic_rag demo` | “This is a bounded ReAct agent, not a free-form chat. It has three read-only tools.” |
| 0:10 | Show `mx01` trace | “It looks up T-1001, gets ALM-1042, then retrieves the alarm procedure. Every step has action, args, observation, latency.” |
| 0:30 | Show `tk01` trace | “For a ticket-only question it does not touch the KB. Tool selection is a first-class metric.” |
| 0:45 | Show `ca01` trace | “Here is a real failure: calculator returns 22.2, then the model emits invalid JSON twice and hits max_steps. Format fragility is the P0, not arithmetic.” |
| 1:00 | `python -m agentic_rag ask --q "ALM-1042 ..." --show-trace` (live, optional) | “Live mode uses the same loop; the trace is written to `runs/`.” |
| 1:15 | Open `eval/comparison.md` | “26 tasks: RAG-only 69.2%, Agent 92.3%; the cost is +4.7s and +1.15 steps.” |
| 1:30 | Stop | “The next step is JSON mode + LLM judge + ACL, not more tools.” |

If the network fails, stay in replay mode. Do not debug live during an interview.

## What to emphasize

1. **The gain is attribution, not magic** — same model/retriever, only tools differ.
2. **The trace is the debugging interface** — a failed answer can be located to a step.
3. **The failure is honest** — `ca01` is a format failure; `KB05` is a judge false
   negative; both are in the report.
4. **Production shell** — auth, rate limit, Docker, CI, health checks are part of the
   repo, not an afterthought.
