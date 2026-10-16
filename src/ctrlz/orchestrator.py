"""Speculative execution for agents.

Production ("main") is never touched by an agent. For each task we fork main N
ways, let one agent loose in each fork, evaluate every fork, and only then move
main to the fork that passed. Discarded forks are deleted. Rolling back is free
because nothing ever happened to main.
"""

from __future__ import annotations

import os
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import context as otel_context
from opentelemetry import trace
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from . import llm, tracing
from .agent import PERSONAS, run_agent
from .boxes import Box, DaytonaBox, LocalBox
from .evals import evaluate, measure

DEFAULT_PERSONAS = ["careful", "rewrite", "aggressive"]


class Orchestrator:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.boxes: dict[str, Box] = {}
        self.busy = False
        self.state: dict = {
            "status": "idle",
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
            "runs": [],
            "native_fork": None,
        }

    # ------------------------------------------------------------------ state helpers

    def snapshot(self) -> dict:
        with self.lock:
            import copy

            return copy.deepcopy(self.state)

    def event(self, msg: str) -> None:
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
            log = self.state["nodes"][nid]["log"]
            log.append({"t": time.time(), "kind": kind, "text": text[:4000]})

    def _status(self, s: str) -> None:
        with self.lock:
            self.state["status"] = s

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

    # ------------------------------------------------------------------ setup

    def setup(self) -> None:
        self._background(self._setup)

    def _setup(self) -> None:
        self._status("setting_up")
        backend = self.state["backend"]
        name = f"ctrlz-main-{uuid.uuid4().hex[:5]}"
        self.event(f"creating production sandbox ({backend})")
        t0 = time.time()
        if backend == "local":
            box = LocalBox.create(name)
        else:
            box = DaytonaBox.create(os.environ.get("CTRLZ_SNAPSHOT", "daytona-small"), name)
        self.event(f"sandbox up in {time.time() - t0:.1f}s; seeding store data and starting server")
        box.boot_app()
        baseline = measure(box)
        nid = "main-0"
        self.boxes[nid] = box
        with self.lock:
            self.state["baseline"] = {k: baseline.get(k) for k in ("latency_ms", "orders", "items", "revenue", "boot_id")}
            self.state["main"] = nid
            self.state["native_fork"] = bool(box.native_fork)
        self.node(nid, parent=None, label="production", persona=None, status="main",
                  sandbox_id=box.sandbox_id, depth=0, created=time.time())
        self.event(f"production ready: orders page takes {baseline.get('latency_ms', 0):,.0f} ms")
        self._prewarm(box)
        self._status("ready")

    # ------------------------------------------------------------------ run

    def run(self, task: str, personas: list[str] | None = None) -> None:
        if not self.state["main"]:
            raise RuntimeError("run setup first")
        self._background(self._run, task, personas or DEFAULT_PERSONAS)

    def _run(self, task: str, personas: list[str]) -> None:
        main_id = self.state["main"]
        main_box = self.boxes[main_id]
        depth = self.state["nodes"][main_id]["depth"] + 1
        run_id = uuid.uuid4().hex[:6]
        with self.lock:
            self.state["runs"].append({"id": run_id, "task": task, "from": main_id, "winner": None})
            baseline = dict(self.state["baseline"])

        tracer = tracing.tracer()
        with tracer.start_as_current_span("ctrlz.run") as run_span:
            run_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
            run_span.set_attribute(SpanAttributes.INPUT_VALUE, task)
            run_span.set_attribute("ctrlz.run_id", run_id)

            # 1. Fork production once per persona.
            self._status("forking")
            ids = [f"{run_id}-{p}" for p in personas]
            for nid, p in zip(ids, personas):
                self.node(nid, parent=main_id, label=PERSONAS[p]["label"], persona=p, status="forking",
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

            def branch(nid: str, persona: str) -> tuple[str, dict]:
                token = otel_context.attach(ctx)
                try:
                    with tracer.start_as_current_span(f"branch:{persona}") as span:
                        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.AGENT.value)
                        span.set_attribute(SpanAttributes.INPUT_VALUE, task)
                        span.set_attribute("ctrlz.persona", persona)
                        span.set_attribute("ctrlz.sandbox_id", self.boxes[nid].sandbox_id)
                        self.node(nid, trace_id=format(span.get_span_context().trace_id, "032x"))
                        result = run_agent(self.boxes[nid], task, persona, lambda k, t: self.log(nid, k, t))
                        self.node(nid, status="evaluating", summary=result.summary, n_commands=len(result.commands))
                        verdict = evaluate(self.boxes[nid], task, result, baseline)
                        span.set_attribute(SpanAttributes.OUTPUT_VALUE, result.summary)
                        span.set_attribute("ctrlz.decision", "keep" if verdict["keep"] else "discard")
                        if not verdict["keep"]:
                            span.set_status(trace.Status(trace.StatusCode.ERROR, verdict["judge"]["risk"]))
                    self.node(nid, status="pass" if verdict["keep"] else "fail", verdict=verdict)
                    self.event(f"{PERSONAS[persona]['label']}: {'KEEP' if verdict['keep'] else 'DISCARD'} - {verdict['judge']['risk']}")
                    return nid, verdict
                except Exception as e:
                    traceback.print_exc()
                    self.node(nid, status="fail", verdict={"keep": False, "error": str(e)})
                    return nid, {"keep": False}
                finally:
                    otel_context.detach(token)

            with ThreadPoolExecutor(len(ids)) as pool:
                results = list(pool.map(lambda a: branch(*a), zip(ids, personas)))

            # 3. Recommend the passing branch the judge trusts most; speed breaks ties.
            passing = [(nid, v) for nid, v in results if v.get("keep")]
            winner = max(passing, key=lambda x: (x[1]["judge"]["score"], x[1]["gates"]["speed"]["speedup"]))[0] if passing else None
            with self.lock:
                self.state["runs"][-1]["winner"] = winner
            run_span.set_attribute("ctrlz.winner", winner or "none")
            run_span.set_attribute(SpanAttributes.OUTPUT_VALUE, winner or "no branch passed")
        if winner:
            self.node(winner, recommended=True)
            self.event(f"recommended: {self.state['nodes'][winner]['label']} - promote it to make it production")
        else:
            self.event("no branch passed; production stays exactly as it was")
        self._prewarm(main_box)
        self._status("review")

    def _prewarm(self, box: Box) -> None:
        if isinstance(box, DaytonaBox) and not box.native_fork:
            DaytonaBox.prewarm(box.snapshot, len(DEFAULT_PERSONAS))

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
        baseline = measure(self.boxes[nid])
        with self.lock:
            self.state["main"] = nid
            self.state["baseline"] = {k: baseline.get(k) for k in ("latency_ms", "orders", "items", "revenue", "boot_id")}
        self.node(nid, status="main", recommended=False)
        self.node(old_main, status="superseded")
        for s in siblings:
            self.node(s["id"], status="discarded")
            box = self.boxes.pop(s["id"], None)
            if box:
                threading.Thread(target=self._safe_delete, args=(box,), daemon=True).start()
        self.event(f"production is now {n['label']} ({baseline.get('latency_ms', 0):,.0f} ms); {len(siblings)} other forks deleted")
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
