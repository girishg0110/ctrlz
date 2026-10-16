# Ctrl+Z: speculative execution for agents

Agents make mistakes. In July 2025 a coding agent deleted a company's production
database during a code freeze. Ctrl+Z makes sure agent mistakes never reach production.

**Agents never touch production.** For each task, Ctrl+Z forks the production
sandbox several ways with Daytona and runs one agent per fork, each with a
different engineering style. Every fork then has to pass the same checks:

- **Integrity:** no data lost.
- **Correctness:** the dashboard still shows the right orders.
- **Speed:** the page got at least 2x faster.
- **LLM judge:** a final keep-or-discard call on the whole change.

Each decision is traced in Arize. Production moves forward only to a fork that
passed, and the losing forks are deleted. Rolling back costs nothing, because
production never changed.

## Demo

1. Production is a store admin app. Its orders page takes about 2 s because of a missing index.
2. The task is *"The orders page is slow. Fix it."* Ctrl+Z forks production into 3 copies:
   - **Careful DBA** measures first and adds the right index.
   - **App-level rewrite** tries to fix the problem in code.
   - **Aggressive cleanup** shrinks the data. It deletes most of the order history.
3. The evals mark Aggressive cleanup red: 77% of orders deleted. Click it to open that fork's live, broken store. Click back: production is untouched.
4. Promote the winner. Production is now about 1,000x faster, with zero rows lost.

## Run

```bash
cp .env.example .env.local   # add keys
uv run ctrlz                 # http://localhost:7860
```

To work offline with no API keys, run `CTRLZ_BACKEND=local CTRLZ_AGENT=scripted uv run ctrlz`.
In that mode the sandboxes are local folders and the agents replay fixed command lists.

## How it uses the sponsors

| Tool | Role |
|---|---|
| **Daytona** | Production and every branch are sandboxes. On Linux VM sandboxes, `sandbox.fork()` copies disk **and memory** in under a second, so the running server carries on in each fork. Container sandboxes fall back to copying files into fresh sandboxes. Live previews of each fork come through `get_preview_link`. |
| **Arize AX** | One trace per run. Each branch is an AGENT span containing the LLM spans (OpenInference OpenAI auto-instrumentation) and a TOOL span for every shell command. An EVALUATOR span records `eval.integrity`, `eval.correctness`, `eval.speed` and `eval.judge` labels with explanations. |
| **Fireworks AI** (Kimi K3) | Runs the agent in each fork (bash tool calling) and acts as the release-gate judge (JSON-schema output), via the OpenAI-compatible API. |

## Layout

```
demo_app/            the "production" store (stdlib only): server.py, seed.py
src/ctrlz/
  boxes.py           Daytona / local sandbox backends, fork + copy-fork
  llm.py             Fireworks client (OpenAI-compatible)
  agent.py           bash-tool agent loop per fork, engineering styles
  evals.py           integrity / correctness / speed gates + LLM judge -> Arize
  check_script.py    measurement harness uploaded fresh into each fork
  orchestrator.py    fork -> run agents in parallel -> evaluate -> recommend -> promote
  web.py, static/    FastAPI + fork-tree dashboard
scripts/smoke_daytona.py   checks an account can create, boot, fork and preview
```
