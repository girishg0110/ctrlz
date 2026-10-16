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

### Option A: the demo, offline, no accounts (2 minutes)

Sandboxes are local folders and the agents replay the scripts in the example config,
so you can see the whole flow (fork tree, checks, verdicts, promotion) without API keys.

```bash
CTRLZ_BACKEND=local CTRLZ_AGENT=scripted uv run ctrlz serve
```

### Option B: the demo on Daytona with real agents

Copy `.env.example` to `.env.local` and fill in:

| Variable | Needed? | Where to get it |
|---|---|---|
| `DAYTONA_API_KEY` | yes | [app.daytona.io](https://app.daytona.io) → API Keys |
| `FIREWORKS_AI_API_KEY` | yes | [fireworks.ai](https://fireworks.ai) → API Keys |
| `ARIZE_SPACE_ID`, `ARIZE_AI_API_KEY` | optional, for tracing | [app.arize.com](https://app.arize.com) → Space Settings |

```bash
uv run ctrlz serve                        # dashboard at http://localhost:7860
uv run ctrlz run "The orders page is slow. Fix it."   # or headless, prints a report
```

In the dashboard: **Start production sandbox**, then **Fork & run**. Click any branch to see
its agent's commands, its checks, the judge's verdict and its live app. **Promote to
production** on a passing branch; the next task forks from there. **Download patch**
gives you that fork's code changes.

## Use it on your own project

Ctrl+Z is driven by a `ctrlz.toml` that says what production is, how to run it, and what
must not break. [`examples/acme-store/ctrlz.toml`](examples/acme-store/ctrlz.toml) is the
demo's config, commented line by line.

```bash
cd your-project
uv run --project /path/to/ctrlz ctrlz init      # writes a starter ctrlz.toml
# edit it, then:
uv run --project /path/to/ctrlz ctrlz run "Add caching to the /search endpoint"
uv run --project /path/to/ctrlz ctrlz clean    # delete leftover sandboxes if a server was killed
```

What goes in the config:

- **`[source]`**: a local folder (`dir`) or a repo (`git`, `branch`) to put in the production sandbox.
- **`[app]`**: `setup` (install, seed data), `start` (must listen on `$APP_PORT`), `port`, a `health` path, and a `description` the agents read.
- **`[[agents.persona]]`**: one fork per persona. Each has a `style` that steers how its agent works. Set `scripted = true` with a `script` list to make a chaos agent that always runs fixed (e.g. destructive) commands, to prove your checks catch it.
- **`[[check]]`**: shell commands that run in production (for a baseline) and in every fork. A check passes on exit code 0. With `compare`, the JSON it prints on its last line is compared with production's: `equal` (nothing may change, e.g. row counts), `no_decrease`, `no_increase`, or `faster` with a `factor` (e.g. latency must halve). Check scripts in `checks_dir` are uploaded fresh at check time, so agents can't edit them.
- **`[diff] ignore`**: files left out of patches (data, logs).

A fork is kept only if every check passes and the LLM judge (which sees the commands, the
diff and the check results) says keep. Every fork's `changes.patch`, `commands.sh` and
`verdict.json` are written to `.ctrlz/runs/<run>/<persona>/`, so you can apply the winning
change to your real system yourself. Ctrl+Z never touches anything outside its sandboxes.

### Settings

| Variable | Default | Effect |
|---|---|---|
| `CTRLZ_CONFIG` | `./ctrlz.toml`, else the example | Config file (or pass it as an argument). |
| `CTRLZ_SNAPSHOT` | `daytona-small` | Daytona snapshot. Use `daytona-vm-small` if your org has Linux VM sandboxes, to get native `sandbox.fork()` (disk + memory). |
| `CTRLZ_BACKEND` | `daytona` | `local` runs sandboxes as temp folders on your machine. |
| `CTRLZ_AGENT` | `llm` | `scripted` replays each persona's `script` instead of calling a model. |
| `CTRLZ_MODEL` | `accounts/fireworks/routers/kimi-k3-fast` | Agent model (any Fireworks model with tool calling). |
| `CTRLZ_JUDGE_MODEL` | same as agent | Judge model (needs JSON-schema output). |
| `CTRLZ_MAX_TURNS` | from config, else `10` | Turn limit per agent. |
| `CTRLZ_OUT` | `.ctrlz/runs` | Where patches and verdicts go. |
| `CTRLZ_KEEP_SANDBOXES` | unset | `1` keeps sandboxes when the server stops. |
| `ARIZE_PROJECT_NAME` | `ctrlz` | Arize project for traces. |

`uv run python scripts/smoke_daytona.py [ctrlz.toml]` checks that your Daytona account can
create, boot, fork and preview your app.

### Rebuilding the demo video

`video/` is a [Remotion](https://remotion.dev) project. `video/tools/narrate.py` voices
`video/script.md` with ElevenLabs (needs `ELEVENLABS_API_KEY`), `video/tools/record.py`
records a live run with Playwright, and `video/tools/music.sh` builds the music bed from
GarageBand's Apple Loops. Then `cd video && npm install && npm run render`.

## How it uses the sponsors

| Tool | Role |
|---|---|
| **Daytona** | Production and every branch are sandboxes. On Linux VM sandboxes, `sandbox.fork()` copies disk **and memory** in under a second, so the running server carries on in each fork. Container sandboxes fall back to copying files into fresh sandboxes. Live previews of each fork come through `get_preview_link`. |
| **Arize AX** | One trace per run. Each branch is an AGENT span containing the LLM spans (OpenInference OpenAI auto-instrumentation) and a TOOL span for every shell command. An EVALUATOR span records an `eval.<check>` label and explanation for every check, plus `eval.judge`. |
| **Fireworks AI** (Kimi K3) | Runs the agent in each fork (bash tool calling) and acts as the release-gate judge (JSON-schema output), via the OpenAI-compatible API. |

## Layout

```
examples/acme-store/   the demo project: ctrlz.toml, app/ (the store), checks/
src/ctrlz/
  config.py            loads ctrlz.toml
  boxes.py             Daytona / local sandbox backends, fork + copy-fork, git baseline and diffs
  llm.py               Fireworks client (OpenAI-compatible)
  agent.py             bash-tool agent loop per fork
  evals.py             runs the config's checks, compares with production, LLM judge -> Arize
  orchestrator.py      fork -> run agents in parallel -> check -> recommend -> promote; saves patches
  web.py, static/      FastAPI + fork-tree dashboard
  __init__.py          CLI: ctrlz init | serve | run
scripts/smoke_daytona.py   checks an account can create, boot, fork and preview
video/                 the demo video (Remotion)
```

## License

MIT. See [LICENSE](LICENSE).
