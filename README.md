# Ctrl+Z: speculative execution for agents

Built by team **random deforestation** at the Daytona HackSprint with Arize AI, NYC, October 2026.

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

## Try it yourself

You need [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 for you).

```bash
git clone https://github.com/girishg0110/ctrlz && cd ctrlz
uv sync
```

### Option A: offline, no accounts (2 minutes)

Sandboxes are local folders and the agents replay fixed command lists, so you can see
the whole flow (fork tree, checks, verdicts, promotion) without any API keys.

```bash
CTRLZ_BACKEND=local CTRLZ_AGENT=scripted uv run ctrlz
```

### Option B: the real thing

Copy `.env.example` to `.env.local` and fill in:

| Variable | Needed? | Where to get it |
|---|---|---|
| `DAYTONA_API_KEY` | yes | [app.daytona.io](https://app.daytona.io) → API Keys |
| `FIREWORKS_AI_API_KEY` | yes | [fireworks.ai](https://fireworks.ai) → API Keys |
| `ARIZE_SPACE_ID`, `ARIZE_AI_API_KEY` | optional, for tracing | [app.arize.com](https://app.arize.com) → Space Settings |

Then:

```bash
uv run python scripts/smoke_daytona.py   # optional: checks your Daytona account works
uv run ctrlz
```

### Using the dashboard

1. Open http://localhost:7860 (or set `PORT`) and click **Start production sandbox** (about 20 s).
2. Keep the task or type your own, then click **Fork & run**. Expect 1–2 minutes.
3. Click any branch to see its agent's commands, its checks and the judge's verdict, and to open that fork's live store on the left.
4. Click **Promote to production** on a passing branch. The next task forks from the new production.

Stopping the server deletes every sandbox it created (set `CTRLZ_KEEP_SANDBOXES=1` to keep them).
Each run uses three short-lived sandboxes and a handful of model calls.

To run once without the browser and print every agent's commands and verdicts:

```bash
uv run python scripts/run_once.py
```

### Settings

| Variable | Default | Effect |
|---|---|---|
| `CTRLZ_SNAPSHOT` | `daytona-small` | Daytona snapshot. Use `daytona-vm-small` if your org has Linux VM sandboxes, to get native `sandbox.fork()` (disk + memory). |
| `CTRLZ_MODEL` | `accounts/fireworks/routers/kimi-k3-fast` | Agent model (any Fireworks model with tool calling). |
| `CTRLZ_JUDGE_MODEL` | same as agent | Judge model (needs JSON-schema output). |
| `CTRLZ_MAX_TURNS` | `10` | Turn limit per agent. |
| `ARIZE_PROJECT_NAME` | `ctrlz` | Arize project for traces. |

### Adapting it to your own system

Right now the "production" system is the demo store in `demo_app/`, and the checks in
`src/ctrlz/check_script.py` and `src/ctrlz/evals.py` are written for it. To guard a
different service: put its code in `demo_app/` (with a `seed.py` that sets up data and a
`server.py` to run), then rewrite the checks to measure what must not break for it.
The agent styles live in `PERSONAS` in `src/ctrlz/agent.py`.

### Rebuilding the demo video

`video/` is a [Remotion](https://remotion.dev) project. `video/tools/narrate.py` voices
`video/script.md` with ElevenLabs (needs `ELEVENLABS_API_KEY`), `video/tools/record.py`
records a live run with Playwright, and `video/tools/music.sh` builds the music bed from
GarageBand's Apple Loops. Then `cd video && npm install && npm run render`.

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
