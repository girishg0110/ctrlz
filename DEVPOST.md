# Devpost submission: Ctrl+Z

**Project name:** Ctrl+Z
**Tagline:** Agents work on copies. Production moves only to a copy that passes.
**Team name:** random deforestation
**Team members:** _add names, emails and socials_
**Repo:** https://github.com/girishg0110/ctrlz
**Demo video:** _add the YouTube or Vimeo link after uploading `video/out/ctrlz-demo-final.mp4`_

---

## Summary

Ctrl+Z lets AI agents change a live system without risking it. For each task it uses Daytona's fork feature to branch production into separate sandboxes, runs one agent in each, and tests every copy for lost data, broken output, speed and safety. Production moves only to a copy that passes; the rest are deleted, so an agent's mistake never reaches customers.

## The problem and its impact

In July 2025, Replit's AI coding agent deleted a company's production database during a code freeze. Agents are now trusted with real systems, and they will keep making mistakes like this. Today the usual safeguards are a human reviewing every step, which defeats the point of an agent, or hoping the agent is careful.

Ctrl+Z takes a different approach: let agents try things, but only on copies, and decide with hard evidence which copy is safe to ship. Running several agents on the same task also raises the odds that one finds a good fix, and the checks pick it out.

In our demo, the task is "The orders page is slow. Fix it." on a store with 200,000 orders. Three agents work in parallel:

- **Careful DBA** adds two missing indexes. The page goes from 2,075 ms to 1 ms with no data lost. Ctrl+Z recommends it.
- **App-level rewrite** rewrites the query and adds a short cache. It passes too, but the judge flags that the cache can show slightly stale orders.
- **Aggressive cleanup** was told to act recklessly (in the live dashboard it is a scripted chaos agent, because Kimi K3 now refuses the destructive playbook). It speeds the page up by deleting 154,150 orders (77%) and $193M of sales history. Ctrl+Z discards it, and production never changes.

Anyone handing real systems to agents could use this, for database migrations, dependency upgrades, infrastructure changes or data cleanups. Ctrl+Z is a reusable tool: a `ctrlz.toml` describes any project (where its code comes from, how to set it up and start it, the agent personas, and the checks that must pass), and `ctrlz run "task"` or the dashboard does the rest, writing the winning fork's patch to disk.

## How it works (architecture)

1. **Production sandbox.** The store (a Python web server with a 1.1M-row SQLite database) runs in a Daytona sandbox. No agent ever runs here.
2. **Fork.** For each task, Ctrl+Z forks production into one sandbox per agent. On Daytona Linux VM sandboxes it uses `sandbox.fork()`, which copies disk and memory in under a second. Our account only had container sandboxes, so Ctrl+Z falls back to copying production's files into pre-created spare sandboxes, which takes about 18 seconds for three copies.
3. **Agents.** Each copy gets an agent (Kimi K3 on Fireworks AI) with a bash tool that runs commands inside that copy's sandbox. The agents share the same task but have different working styles, so their approaches differ.
4. **Checks.** The project's config lists checks as shell commands (test suites, data queries, benchmarks). Each runs in production for a baseline and in every fork; the numbers are compared with production by rule (`equal`, `no_decrease`, `no_increase`, `faster` by a factor). Check scripts are uploaded fresh into each fork, so agents can't tamper with them. The demo's four checks:
   - **Integrity:** no orders, items or revenue lost compared with production.
   - **Correctness:** the dashboard shows the same 40 orders and item counts as an independent query.
   - **Speed:** the orders page is at least twice as fast.
   - **Judge:** a second model call reads the agent's commands and the measured results and returns keep or discard, with a score, the biggest risk and a short reason.
5. **Promote.** Ctrl+Z recommends the passing copy the judge trusts most. One click makes it the new production, and the other copies are deleted. Later tasks copy from the new production, so the history forms a tree.
6. **Tracing.** Every run is one trace in Arize, from the run down to each model call, shell command and verdict.

7. **Output.** Every fork's code diff (`changes.patch`), the commands its agent ran (`commands.sh`) and its verdict are saved, so the winning change can be applied to the real system.

**Components:** Python, FastAPI and a vanilla JS dashboard (fork tree, live agent logs, verdicts, patch download, and a live view of any fork's app through a preview proxy); a CLI (`ctrlz init | serve | run | clean`); `config.py` (project config); `boxes.py` (Daytona backend with native fork and copy fallback, git baseline and diffs); `agent.py` (agent loop); `evals.py` (config-driven checks and judge); `orchestrator.py` (fork, run, evaluate, promote).

## Sponsor tools and how we used them

- **Daytona.** Ctrl+Z is built around Daytona's fork feature: production is a sandbox, and every agent gets its own fork of it via `sandbox.fork()`, tracked as a fork tree. We also use the Python SDK to create sandboxes, run commands (every agent command and every check runs through `process.exec`), move files, and get preview links so the dashboard can show each copy's live store. Forking needs Linux VM sandboxes; while our access request is pending, Ctrl+Z falls back to copying files into pre-warmed container sandboxes, which is what the recorded demo run used.
- **Arize AX.** Ctrl+Z sends OpenTelemetry traces to Arize with OpenInference. Each run is a CHAIN span, and each branch is an AGENT span. Under each branch are the model calls (auto-instrumented), a TOOL span for every shell command with its output, and an EVALUATOR span. The EVALUATOR span records `eval.integrity`, `eval.correctness`, `eval.speed` and `eval.judge` labels, scores and explanations. In Arize you can open the discarded branch and see the exact command that deleted the orders next to the verdict that caught it.
- **ElevenLabs.** We used ElevenLabs text-to-speech, with the Eric voice and word-level timestamps, to narrate our demo video. The timestamps drive the captions and time the animations to the voice. ElevenLabs is used for the video only, not inside the product.
- **Fireworks AI** (not an event sponsor). Runs the agents and the judge on Kimi K3 through its OpenAI-compatible API, using tool calling for the agents and JSON-schema output for the judge.

## Built with

python, fastapi, daytona, arize, openinference, opentelemetry, fireworks-ai, kimi-k3, sqlite, javascript, elevenlabs, remotion, playwright

## What's next

- Native memory forks on Daytona VM sandboxes, so copies take under a second and keep running processes.
- Open the winning fork's change as a pull request automatically.
- A safety mode that blocks known-destructive commands before they run, on top of judging afterwards.
