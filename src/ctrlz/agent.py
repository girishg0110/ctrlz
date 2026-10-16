"""The agent that runs inside one fork: an LLM with a bash tool, executed in that fork's sandbox.

Each fork gets the same task but a different engineering style, so the branches
genuinely diverge. The styles steer *how* the agent works; it still chooses
every command itself.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from . import llm, tracing
from .boxes import Box
from .config import Persona

OUTPUT_LIMIT = 6000

SYSTEM = """You are an autonomous engineer working on a live production system: {name}.

About the system:
{description}

Environment:
- The code lives in {app_dir}. Each bash call runs in a fresh shell starting there.
- The app is running right now on port {port} (also in $APP_PORT). It was started with:
  {start}
  If you change code the running process depends on, stop it and start it again the same way.
- Check it at http://127.0.0.1:{port}{health}. curl may be missing; python3 urllib works.

Your engineering style: {style}

Be fast: use at most 5 commands, combining steps into one script where you can. When you are done, reply with a 2-3 sentence summary of what you changed and why. Do not ask questions; nobody will answer."""

Emit = Callable[[str, str], None]


@dataclass
class AgentResult:
    commands: list[str] = field(default_factory=list)
    summary: str = ""
    turns: int = 0
    stop: str = ""


def _clip(text: str) -> str:
    if len(text) <= OUTPUT_LIMIT:
        return text
    half = OUTPUT_LIMIT // 2
    return f"{text[:half]}\n... [{len(text) - OUTPUT_LIMIT} chars clipped] ...\n{text[-half:]}"


def _run_command(box: Box, command: str, emit: Emit, result: AgentResult) -> str:
    result.commands.append(command)
    emit("cmd", command)
    with tracing.tracer().start_as_current_span("bash") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.TOOL.value)
        span.set_attribute(SpanAttributes.TOOL_NAME, "bash")
        span.set_attribute(SpanAttributes.INPUT_VALUE, command)
        r = box.exec(command, timeout=120)
        out = _clip(r.output.strip()) or "(no output)"
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, out)
        span.set_attribute("ctrlz.exit_code", r.exit_code)
    emit("out", out if r.exit_code == 0 else f"[exit {r.exit_code}] {out}")
    return out if r.exit_code == 0 else f"exit code {r.exit_code}\n{out}"


BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command in the server's sandbox and return its combined stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "The shell command to run."}},
            "required": ["command"],
        },
    },
}


def run_llm(box: Box, task: str, persona: Persona, emit: Emit) -> AgentResult:
    client = llm.client()
    cfg = box.cfg
    system = SYSTEM.format(name=cfg.name, description=cfg.description or "(no description given)", app_dir=box.app_dir,
                           port=box.port, start=cfg.start, health=cfg.health, style=persona.style)
    messages: list = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    result = AgentResult()

    for turn in range(cfg.max_turns):
        result.turns = turn + 1
        response = client.chat.completions.create(
            model=llm.AGENT_MODEL, messages=messages, tools=[BASH_TOOL], max_tokens=8000,
        )
        choice = response.choices[0]
        msg = choice.message
        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning and reasoning.strip():
            emit("think", reasoning.strip())
        if msg.content and msg.content.strip():
            emit("text", msg.content.strip())
            result.summary = msg.content.strip()

        if not msg.tool_calls:
            result.stop = choice.finish_reason or "stop"
            break

        assistant = {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        }
        if reasoning:  # thinking models expect their reasoning back alongside tool calls
            assistant["reasoning_content"] = reasoning
        messages.append(assistant)
        for tc in msg.tool_calls:
            try:
                command = json.loads(tc.function.arguments or "{}").get("command")
            except json.JSONDecodeError:
                command = None
            content = (
                _run_command(box, command, emit, result) if command
                else "Error: call bash with a JSON object like {\"command\": \"ls\"}."
            )
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
    else:
        result.stop = "max_turns"
        emit("text", f"[stopped after {cfg.max_turns} turns]")
    return result


# Offline stand-in used when CTRLZ_AGENT=scripted (no API key needed). It replays the
# persona's `script` from the config so the UI and checks can be exercised end to end.
def run_scripted(box: Box, task: str, persona: Persona, emit: Emit) -> AgentResult:
    result = AgentResult()
    for cmd in persona.script:
        result.turns += 1
        _run_command(box, cmd, emit, result)
    result.summary = f"[scripted {persona.name} agent] replayed {len(result.commands)} fixed commands from the config."
    emit("text", result.summary)
    result.stop = "end_turn"
    return result


def run_agent(box: Box, task: str, persona: Persona, emit: Emit) -> AgentResult:
    if persona.scripted or os.environ.get("CTRLZ_AGENT", "llm") == "scripted":
        return run_scripted(box, task, persona, emit)
    return run_llm(box, task, persona, emit)


def transcript_for_judge(result: AgentResult) -> str:
    return json.dumps({"commands": result.commands, "agent_summary": result.summary, "stop": result.stop}, indent=1)
