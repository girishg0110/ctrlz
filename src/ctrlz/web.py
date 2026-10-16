"""Web UI + API. Run with `uv run ctrlz serve [ctrlz.toml]` and open http://localhost:7860."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
for env_file in (Path.cwd() / ".env.local", Path.cwd() / ".env", ROOT / ".env.local", ROOT / ".env"):
    load_dotenv(env_file)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import tracing  # noqa: E402

tracing.setup()

from . import config  # noqa: E402
from .boxes import http_get  # noqa: E402
from .orchestrator import Orchestrator  # noqa: E402

app = FastAPI(title="Ctrl+Z")
orc = Orchestrator(config.load())
STATIC = Path(__file__).parent / "static"


class RunReq(BaseModel):
    task: str
    personas: list[str] | None = None


class NodeReq(BaseModel):
    node: str


def _guard(fn, *args):
    try:
        fn(*args)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
def state():
    s = orc.snapshot()
    s["busy"] = orc.busy
    return JSONResponse(s)


@app.post("/api/setup")
def setup():
    return _guard(orc.setup)


@app.post("/api/run")
def run(req: RunReq):
    return _guard(orc.run, req.task, req.personas)


@app.post("/api/promote")
def promote(req: NodeReq):
    return _guard(orc.promote, req.node)


@app.get("/api/patch/{nid}")
def patch(nid: str):
    n = orc.snapshot()["nodes"].get(nid) or {}
    diff = (n.get("verdict") or {}).get("diff")
    if diff is None:
        raise HTTPException(404, "no patch for this node")
    return Response(diff or "# no code changes (see commands for data changes)\n", media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="ctrlz-{nid}.patch"'})


@app.get("/preview/{nid}/{path:path}")
def preview(nid: str, path: str = ""):
    box = orc.boxes.get(nid)
    if not box:
        return Response(
            "<body style='font:14px system-ui;display:grid;place-items:center;height:90vh;color:#888'>"
            "This fork was discarded and its sandbox deleted.</body>", media_type="text/html")
    url, headers = box.preview()
    code, body, ctype = http_get(f"{url}/{path}", headers)
    return Response(body, status_code=code, media_type=ctype.split(";")[0])


def main():
    import uvicorn

    port = int(os.environ.get("PORT", 7860))
    print(f"[ctrlz] open http://localhost:{port}")
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
    finally:
        if os.environ.get("CTRLZ_KEEP_SANDBOXES") != "1":
            print("[ctrlz] deleting sandboxes")
            orc.teardown()
