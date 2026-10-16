"""Speculative execution for agents.

Production ("main") is never touched by an agent. For each task we fork main once per
persona, let one agent loose in each fork, check every fork, and only then move main to
a fork that passed. Discarded forks are deleted. Rolling back is free because nothing
ever happened to main. Every fork's code diff, commands and verdict are saved to
.ctrlz/runs/<run>/<persona>/ so the winning change can be applied outside Ctrl+Z.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from opentelemetry import context as otel_context
from opentelemetry import trace
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from . import llm, tracing
from .agent import run_agent
from .boxes import Box, DaytonaBox, LocalBox
from .config import Config
from .evals import evaluate, measure

OUT_DIR = Path(os.environ.get("CTRLZ_OUT", ".ctrlz/runs"))


def headline_value(cfg: Config, metrics: dict) -> float | None:
    h = cfg.headline
    if not h or h.name not in metrics or not metrics[h.name]:
        return None
    return next(iter(metrics[h.name].values()))


class Orchestrator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.lock = threading.RLock()
        self.boxes: dict[str, Box] = {}
        self.busy = False
        self.state: dict = {
            "status": "idle",
            "project": cfg.name,
            "config": str(cfg.path),
            "task": cfg.task,
            "personas": {p.name: p.label for p in cfg.personas},
            "checks": [c.name for c in cfg.checks],
            "headline": cfg.headline.name if cfg.headline else None,
            "backend": os.environ.get("CTRLZ_BACKEND", "daytona"),
            "agent": os.environ.get("CTRLZ_AGENT", "llm"),
            "agent_model": llm.short(llm.AGENT_MODEL),
            "judge_model": llm.short(llm.JUDGE_MODEL),
            "arize": tracing.enabled(),
            "arize_project": tracing.PROJECT,
            "main": None,
            "nodes": {},
            "events": [],
            "baseline": None,
            "baseline_headline": None,
            "runs": [],
            "native_fork": None,
        }

    # ------------------------------------------------------------------ state helpers

    def snapshot(self) -> dict:
        with self.lock:
            return copy.deepcopy(self.state)

    def event(self, msg: str) -> None:
        print(f"[ctrlz] {msg}", flush=True)
        with self.lock:
            self.state["events"].append({"t": time.time(), "msg": msg})
            self.state["events"] = self.state["events"][-200:]

    def node(self, nid: str, **updates) -> dict:
        with self.lock:
            n = self.state["nodes"].setdefault(nid, {"id": nid, "log": []})
            n.update(updates)
            return n

    def log(self, nid: str, kind: str, text: str) -> None:
        with self.lock:
            self.state["nodes"][nid]["log"].append({"t": time.time(), "kind": kind, "text": text[:4000]})

    def _status(self, s: str) -> None:
        with self.lock:
            self.state["status"] = s

    def _set_baseline(self, metrics: dict) -> None:
        with self.lock:
            self.state["baseline"] = metrics
            self.state["baseline_headline"] = headline_value(self.cfg, {k: v["metrics"] for k, v in metrics.items()})

    def _background(self, fn, *args) -> None:
        with self.lock:
            if self.busy:
                raise RuntimeError("busy")
            self.busy = True

        def wrapped():
            try:
                fn(*args)
            except Exception as e:
                traceback.print_exc()
                self.event(f"error: {e}")
                self._status("error")
            finally:
                with self.lock:
                    self.busy = False

        threading.Thread(target=wrapped, daemon=True).start()

    def wait(self) -> dict:
        while self.busy:
            time.sleep(0.5)
        return self.snapshot()

    # ------------------------------------------------------------------ setup

    def setup(self) -> None:
        self._background(self._setup)

    def _setup(self) -> None:
        self._status("setting_up")
        backend = self.state["backend"]
        name = f"ctrlz-main-{uuid.uuid4().hex[:5]}"
        self.event(f"creating production sandbox for {self.cfg.name} ({backend})")
        t0 = time.time()
        if backend == "local":
            box = LocalBox.create(self.cfg, name)
        else:
            box = DaytonaBox.create(self.cfg, os.environ.get("CTRLZ_SNAPSHOT", "daytona-small"), name)
        self.event(f"sandbox up in {time.time() - t0:.1f}s; running setup and starting the app")
        box.boot_app()
        baseline = measure(box)
        failed = [k for k, v in baseline.items() if v["exit"] != 0]
        if failed:
            raise RuntimeError(f"checks fail on production itself, fix them first: {', '.join(failed)}")
        nid = "main-0"
        self.boxes[nid] = box
        self._set_baseline(baseline)
        with self.lock:
            self.state["main"] = nid
            self.state["native_fork"] = bool(box.native_fork)
        self.node(nid, parent=None, label="production", persona=None, status="main",
                  sandbox_id=box.sandbox_id, depth=0, created=time.time())
        hv = self.state["baseline_headline"]
        hm = next(iter(baseline[self.cfg.headline.name]["metrics"]), "") if self.cfg.headline else ""
        self.event("production ready" + (f": {hm} {hv:,.0f}" if hv is not None else ""))
        self._prewarm(box)
        self._status("ready")

    # ------------------------------------------------------------------ run

    def run(self, task: str, personas: list[str] | None = None) -> None:
        if not self.state["main"]:
            raise RuntimeError("run setup first")
        chosen = [p for p in self.cfg.personas if not personas or p.name in personas]
        self._background(self._run, task or self.cfg.task, chosen)

    def _run(self, task: str, personas: list) -> None:
        main_id = self.state["main"]
        main_box = self.boxes[main_id]
        depth = self.state["nodes"][main_id]["depth"] + 1
        run_id = uuid.uuid4().hex[:6]
        with self.lock:
            self.state["runs"].append({"id": run_id, "task": task, "from": main_id, "winner": None})
            baseline = copy.deepcopy(self.state["baseline"])

        tracer = tracing.tracer()
        with tracer.start_as_current_span("ctrlz.run") as run_span:
            run_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
            run_span.set_attribute(SpanAttributes.INPUT_VALUE, task)
            run_span.set_attribute("ctrlz.run_id", run_id)
            run_span.set_attribute("ctrlz.project", self.cfg.name)

            # 1. Fork production once per persona.
            self._status("forking")
            ids = [f"{run_id}-{p.name}" for p in personas]
            for nid, p in zip(ids, personas):
                self.node(nid, parent=main_id, label=p.label, persona=p.name, status="forking",
                          depth=depth, run_id=run_id, created=time.time())
            kind = "native fork (disk + memory)" if main_box.native_fork else "copy-fork (files only)"
            self.event(f"forking production x{len(personas)} via {kind}")
            t0 = time.time()
            children = main_box.fork_many([f"ctrlz-{nid}" for nid in ids])
            fork_s = time.time() - t0
            self.event(f"{len(children)} forks ready in {fork_s:.1f}s")
            for nid, child in zip(ids, children):
                self.boxes[nid] = child
                self.node(nid, status="running", sandbox_id=child.sandbox_id, fork_s=round(fork_s / len(children), 2))

            # 2. One agent per fork, in parallel, each in its own Arize branch span.
            self._status("running")
            ctx = otel_context.get_current()

            def branch(nid: str, persona) -> tuple[str, dict]:
                token = otel_context.attach(ctx)
                try:
                    with tracer.start_as_current_span(f"branch:{persona.name}") as span:
                        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.AGENT.value)
                        span.set_attribute(SpanAttributes.INPUT_VALUE, task)
                        span.set_attribute("ctrlz.persona", persona.name)
                        span.set_attribute("ctrlz.sandbox_id", self.boxes[nid].sandbox_id)
                        self.node(nid, trace_id=format(span.get_span_context().trace_id, "032x"))
                        result = run_agent(self.boxes[nid], task, persona, lambda k, t: self.log(nid, k, t))
                        self.node(nid, status="evaluating", summary=result.summary, n_commands=len(result.commands))
                        verdict = evaluate(self.boxes[nid], task, result, baseline)
                        verdict["headline"] = headline_value(self.cfg, verdict["metrics"])
                        span.set_attribute(SpanAttributes.OUTPUT_VALUE, result.summary)
                        span.set_attribute("ctrlz.decision", "keep" if verdict["keep"] else "discard")
                        if not verdict["keep"]:
                            span.set_status(trace.Status(trace.StatusCode.ERROR, verdict["judge"]["risk"]))
                    self._save(run_id, persona.name, task, result, verdict)
                    self.node(nid, status="pass" if verdict["keep"] else "fail", verdict=verdict)
                    self.event(f"{persona.label}: {'KEEP' if verdict['keep'] else 'DISCARD'} - {verdict['judge']['risk']}")
                    return nid, verdict
                except Exception as e:
                    traceback.print_exc()
                    self.node(nid, status="fail", verdict={"keep": False, "error": str(e)})
                    return nid, {"keep": False}
                finally:
                    otel_context.detach(token)

            with ThreadPoolExecutor(len(ids)) as pool:
                results = list(pool.map(lambda a: branch(*a), zip(ids, personas)))

            # 3. Recommend the passing branch the judge trusts most; the headline metric breaks ties.
            def rank(item):
                v = item[1]
                ratio = next((g.get("ratio", 0) for g in v["gates"] if g["name"] == self.state["headline"]), 0)
                return (v["judge"]["score"], ratio)

            passing = [(nid, v) for nid, v in results if v.get("keep")]
            winner = max(passing, key=rank)[0] if passing else None
            with self.lock:
                self.state["runs"][-1]["winner"] = winner
            run_span.set_attribute("ctrlz.winner", winner or "none")
            run_span.set_attribute(SpanAttributes.OUTPUT_VALUE, winner or "no branch passed")
        if winner:
            self.node(winner, recommended=True)
            self.event(f"recommended: {self.state['nodes'][winner]['label']} - patch in {OUT_DIR / run_id / winner.split('-', 1)[1]}")
        else:
            self.event("no branch passed; production stays exactly as it was")
        self._prewarm(main_box)
        self._status("review")

    def _save(self, run_id: str, persona: str, task: str, result, verdict: dict) -> None:
        d = OUT_DIR / run_id / persona
        d.mkdir(parents=True, exist_ok=True)
        (d / "changes.patch").write_text(verdict.get("diff", ""))
        (d / "commands.sh").write_text("#!/usr/bin/env bash\n# Commands the agent ran, in order (data changes live here, not in the patch).\n"
                                       + "\n".join(result.commands) + "\n")
        (d / "verdict.json").write_text(json.dumps({
            "project": self.cfg.name, "task": task, "persona": persona, "keep": verdict["keep"],
            "checks": verdict["gates"], "judge": verdict["judge"], "agent_summary": result.summary,
        }, indent=1))

    def _prewarm(self, box: Box) -> None:
        if isinstance(box, DaytonaBox) and not box.native_fork:
            DaytonaBox.prewarm(self.cfg, box.snapshot, len(self.cfg.personas))

    # ------------------------------------------------------------------ promote / discard

    def promote(self, nid: str) -> None:
        self._background(self._promote, nid)

    def _promote(self, nid: str) -> None:
        with self.lock:
            n = self.state["nodes"][nid]
            old_main = self.state["main"]
            run_id = n.get("run_id")
            siblings = [x for x in self.state["nodes"].values() if x.get("run_id") == run_id and x["id"] != nid]
        self.event(f"promoting {n['label']} to production")
        box = self.boxes[nid]
        # The promoted fork's state becomes the new baseline, for checks and for diffs.
        from .boxes import GIT
        box.exec(f"{GIT} add -A && {GIT} commit -qm 'ctrlz: promote {n['label']}' --allow-empty", timeout=120)
        self._set_baseline(measure(box))
        with self.lock:
            self.state["main"] = nid
        self.node(nid, status="main", recommended=False)
        self.node(old_main, status="superseded")
        for s in siblings:
            self.node(s["id"], status="discarded")
            b = self.boxes.pop(s["id"], None)
            if b:
                threading.Thread(target=self._safe_delete, args=(b,), daemon=True).start()
        hv = self.state["baseline_headline"]
        self.event(f"production is now {n['label']}" + (f" ({hv:,.0f})" if hv is not None else "") + f"; {len(siblings)} other forks deleted")
        self._status("ready")

    @staticmethod
    def _safe_delete(box: Box) -> None:
        try:
            box.delete()
        except Exception as e:  # parents with live forks cannot be deleted; fine to leave
            print(f"[ctrlz] delete {box.name} skipped: {e}")

    def teardown(self) -> None:
        for box in list(self.boxes.values())[::-1]:
            self._safe_delete(box)
        self.boxes.clear()
        DaytonaBox.drain_warm()
