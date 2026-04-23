from __future__ import annotations

import json
import queue
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.config import (
    KeywordRule,
    RunConfig,
    TextRule,
    _config_from_dict,
    _config_to_dict,
    list_profiles,
    load_profile,
    save_profile,
)
from core.filler import run_all

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Form Auto-Filler")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Session state ─────────────────────────────────────────────────────────────

@dataclass
class SessionState:
    sid: str
    status: str = "idle"          # idle | running | done | stopped | error
    log_queue: queue.Queue = field(default_factory=queue.Queue)
    history: list[dict] = field(default_factory=list)
    thread: Thread | None = None
    stop_event: Event | None = None
    driver_ref: list = field(default_factory=list)
    current_run: dict = field(default_factory=dict)  # {success, fail, total}


sessions: dict[str, SessionState] = {}


def _get_or_create_session(sid: str | None) -> SessionState:
    if sid and sid in sessions:
        return sessions[sid]
    new_sid = sid or str(uuid.uuid4())
    sessions[new_sid] = SessionState(sid=new_sid)
    return sessions[new_sid]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/session")
def create_session(sid: str | None = None):
    sess = _get_or_create_session(sid)
    return {"sid": sess.sid}


@app.get("/api/status/{sid}")
def get_status(sid: str):
    if sid not in sessions:
        raise HTTPException(404, "Session not found")
    s = sessions[sid]
    return {
        "status": s.status,
        "progress": s.current_run,
    }


@app.post("/api/run/{sid}")
def start_run(sid: str, body: dict):
    if sid not in sessions:
        raise HTTPException(404, "Session not found")
    s = sessions[sid]
    if s.status == "running":
        raise HTTPException(409, "Already running")

    # Parse RunConfig from request body
    try:
        config = _config_from_dict(dict(body))
    except Exception as e:
        raise HTTPException(400, f"Invalid config: {e}")

    # Prepare run state
    s.stop_event = Event()
    s.driver_ref = []
    s.status = "running"
    s.current_run = {"success": 0, "fail": 0, "total": config.n_submissions}

    # Flush old queue
    while not s.log_queue.empty():
        try:
            s.log_queue.get_nowait()
        except Exception:
            pass

    run_logs: list[str] = []

    def log_fn(msg: str) -> None:
        s.log_queue.put(msg)
        run_logs.append(msg)

    def runner():
        try:
            result = run_all(
                config,
                log_fn=log_fn,
                stop_event=s.stop_event,
                driver_ref=s.driver_ref,
            )
            s.current_run["success"] = result["success"]
            s.current_run["fail"] = result["fail"]
            s.status = "done" if not s.stop_event.is_set() else "stopped"
        except Exception as e:
            log_fn(f"[red]❌ Lỗi nghiêm trọng: {e}[/red]")
            s.status = "error"
        finally:
            # Add to history
            s.history.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "url": config.form_url,
                "n_submissions": config.n_submissions,
                "success": s.current_run.get("success", 0),
                "fail": s.current_run.get("fail", 0),
                "logs": list(run_logs),
            })
            s.log_queue.put("__DONE__")

    s.thread = Thread(target=runner, daemon=True)
    s.thread.start()
    return {"ok": True}


@app.get("/api/stream/{sid}")
def stream_logs(sid: str):
    if sid not in sessions:
        raise HTTPException(404, "Session not found")
    s = sessions[sid]

    def generator():
        while True:
            try:
                msg = s.log_queue.get(timeout=0.5)
                payload = json.dumps({"msg": msg}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                if msg == "__DONE__":
                    break
            except queue.Empty:
                yield ": keepalive\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/stop/{sid}")
def stop_run(sid: str):
    if sid not in sessions:
        raise HTTPException(404, "Session not found")
    s = sessions[sid]
    if s.stop_event:
        s.stop_event.set()
    # Force quit driver if alive
    if s.driver_ref:
        try:
            s.driver_ref[0].quit()
        except Exception:
            pass
    s.status = "stopped"
    return {"ok": True}


@app.get("/api/history/{sid}")
def get_history(sid: str):
    if sid not in sessions:
        raise HTTPException(404, "Session not found")
    return {"history": sessions[sid].history}


# ── Profile routes ────────────────────────────────────────────────────────────

@app.get("/api/profiles")
def get_profiles():
    return {"profiles": list_profiles()}


@app.get("/api/profiles/{name}")
def get_profile(name: str):
    try:
        cfg = load_profile(name)
        return _config_to_dict(cfg)
    except Exception as e:
        raise HTTPException(404, str(e))


@app.post("/api/profiles/{name}")
def create_profile(name: str, body: dict):
    try:
        config = _config_from_dict(dict(body))
        path = save_profile(config, name)
        return {"ok": True, "path": str(path)}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.delete("/api/profiles/{name}")
def delete_profile(name: str):
    from core.config import PROFILES_DIR
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, "Profile not found")
    path.unlink()
    return {"ok": True}
