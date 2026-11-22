# Publishing

This directory is already a standalone project; it does not import anything from the
parent workspace. To publish it as its own GitHub repository:

```bash
cd AgenticRAG

# 1) sanity checks
python -m pytest -q
ruff check src tests
git status --short

# 2) create the repo (choose a name)
git init
git add .
git commit -m "feat: bounded ReAct agent with FastAPI/Docker/CI"

# 3) create a public GitHub repo and push
gh repo create agentic-rag --public --source=. --remote=origin --push
```

If you prefer to create the repo in the browser, create an empty repository first and
run:

```bash
git remote add origin git@github.com:<you>/agentic-rag.git
git branch -M main
git push -u origin main
```

## Before publishing

- [ ] `.env` is not staged (`git status` should not show it).
- [ ] `runs/` and evaluation scratch files are ignored.
- [ ] The bundled data is illustrative; no proprietary company documents.
- [ ] `LICENSE` matches your intent (MIT by default).
- [ ] Replace the example `API_KEYS`; never commit real keys.
- [ ] If you rename the repo, update the README title/badges if desired.

## What is committed

- `src/agentic_rag/` — package;
- `data/` — bundled docs, indexes, mock tickets, tasks, demo traces;
- `tests/`, `docs/`, `scripts/`;
- `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`.

`eval/report.json` and the Markdown reports are reference evidence; regenerate them
with `python -m agentic_rag eval --mode both --runs 1` if you change the model or prompts.
