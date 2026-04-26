from __future__ import annotations

import json
import queue
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Event, Thread

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.config import _config_from_dict, _config_to_dict, list_profiles, load_profile, save_profile
from core.filler import run_all
from web.auth import create_token, require_admin, require_auth, verify_password, verify_token
from web.db import (
    create_user,
    decrement_quota,
    delete_user,
    get_user_by_id,
    get_user_by_username,
    increment_total,
    init_db,
    list_users,
    search_users,
    update_quota,
)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Form Auto-Filler")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@dataclass
class SessionState:
    sid: str
    owner_id: int
    status: str = "idle"  # idle | running | done | stopped | error
    log_queue: queue.Queue = field(default_factory=queue.Queue)
    history: list[dict] = field(default_factory=list)
    thread: Thread | None = None
    stop_event: Event | None = None
    driver_ref: list = field(default_factory=list)
    current_run: dict = field(default_factory=lambda: {"success": 0, "fail": 0, "total": 0})


sessions: dict[str, SessionState] = {}


@app.on_event("startup")
def on_startup() -> None:
    seeded = init_db()
    if seeded:
        print("Admin mặc định đã được tạo: admin/admin1")


def _serialize_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "quota_remaining": user["quota_remaining"],
        "total_submitted": user["total_submitted"],
        "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
    }


def _coerce_quota(value) -> int | None:
    if value in (None, "", "null"):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "Quota phải là số nguyên không âm hoặc để trống") from exc


def _get_or_create_session(requested_sid: str | None, owner_id: int) -> SessionState:
    if requested_sid and requested_sid in sessions:
        existing = sessions[requested_sid]
        if existing.owner_id == owner_id:
            return existing
    new_sid = str(uuid.uuid4())
    session = SessionState(sid=new_sid, owner_id=owner_id)
    sessions[new_sid] = session
    return session


def _get_session_for_user(sid: str, user: dict) -> SessionState:
    if sid not in sessions:
        raise HTTPException(404, "Session not found")
    session = sessions[sid]
    if session.owner_id != user["id"]:
        raise HTTPException(403, "Bạn không có quyền truy cập session này")
    return session


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/auth/login")
def login(body: dict):
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    if not username or not password:
        raise HTTPException(400, "Cần nhập username và password")

    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Sai username hoặc password")

    token = create_token(user["id"], user["username"], user["role"])
    return {"token": token, "user": _serialize_user(user)}


@app.get("/api/me")
def me(user: dict = Depends(require_auth)):
    record = get_user_by_id(user["id"])
    if not record:
        raise HTTPException(401, "User không còn tồn tại")
    return _serialize_user(record)


@app.post("/api/session")
def create_session(body: dict | None = None, user: dict = Depends(require_auth)):
    requested_sid = None if body is None else body.get("sid")
    session = _get_or_create_session(requested_sid, user["id"])
    return {"sid": session.sid}


@app.get("/api/status/{sid}")
def get_status(sid: str, user: dict = Depends(require_auth)):
    session = _get_session_for_user(sid, user)
    return {"status": session.status, "progress": session.current_run}


@app.post("/api/run/{sid}")
def start_run(sid: str, body: dict, user: dict = Depends(require_auth)):
    session = _get_session_for_user(sid, user)
    if session.status == "running":
        raise HTTPException(409, "Already running")

    try:
        config = _config_from_dict(dict(body))
    except Exception as exc:
        raise HTTPException(400, f"Invalid config: {exc}") from exc

    record = get_user_by_id(user["id"])
    if not record:
        raise HTTPException(401, "User không còn tồn tại")

    requested_total = config.n_submissions
    if user["role"] != "admin":
        remaining = record["quota_remaining"]
        if remaining is not None and remaining <= 0:
            raise HTTPException(403, "Hết quota")
        if remaining is not None and remaining < config.n_submissions:
            config.n_submissions = remaining

    session.stop_event = Event()
    session.driver_ref = []
    session.status = "running"
    session.current_run = {"success": 0, "fail": 0, "total": config.n_submissions}

    while not session.log_queue.empty():
        try:
            session.log_queue.get_nowait()
        except Exception:
            break

    run_logs: list[str] = []

    def log_fn(message: str) -> None:
        session.log_queue.put(message)
        run_logs.append(message)

    if config.n_submissions != requested_total:
        log_fn(
            f"[yellow]⚠ Quota còn {config.n_submissions} lượt, giảm số lần chạy từ "
            f"{requested_total} xuống {config.n_submissions}[/yellow]"
        )

    def progress_fn(success: int, fail: int, total: int) -> None:
        session.current_run = {"success": success, "fail": fail, "total": total}

    def quota_fn() -> None:
        remaining = decrement_quota(user["id"])
        increment_total(user["id"])
        if remaining == 0 and session.stop_event:
            session.stop_event.set()

    def runner() -> None:
        try:
            result = run_all(
                config,
                log_fn=log_fn,
                stop_event=session.stop_event,
                driver_ref=session.driver_ref,
                quota_fn=quota_fn if user["role"] != "admin" else None,
                progress_fn=progress_fn,
            )
            session.current_run["success"] = result["success"]
            session.current_run["fail"] = result["fail"]
            if session.status != "error":
                session.status = "done" if not session.stop_event or not session.stop_event.is_set() else "stopped"
        except Exception as exc:
            log_fn(f"[red]❌ Lỗi nghiêm trọng: {exc}[/red]")
            session.status = "error"
        finally:
            session.history.append(
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "url": config.form_url,
                    "n_submissions": config.n_submissions,
                    "success": session.current_run.get("success", 0),
                    "fail": session.current_run.get("fail", 0),
                    "logs": list(run_logs),
                }
            )
            session.log_queue.put("__DONE__")

    session.thread = Thread(target=runner, daemon=True)
    session.thread.start()
    return {"ok": True, "effective_submissions": config.n_submissions}


@app.get("/api/stream/{sid}")
def stream_logs(sid: str, token: str = Query(...)):
    user = verify_token(token)
    session = _get_session_for_user(sid, user)

    def generator():
        while True:
            try:
                message = session.log_queue.get(timeout=0.5)
                payload = json.dumps({"msg": message}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                if message == "__DONE__":
                    break
            except queue.Empty:
                yield ": keepalive\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/stop/{sid}")
def stop_run(sid: str, user: dict = Depends(require_auth)):
    session = _get_session_for_user(sid, user)
    if session.stop_event:
        session.stop_event.set()
    if session.driver_ref:
        try:
            session.driver_ref[0].quit()
        except Exception:
            pass
    session.status = "stopped"
    return {"ok": True}


@app.get("/api/history/{sid}")
def get_history(sid: str, user: dict = Depends(require_auth)):
    session = _get_session_for_user(sid, user)
    return {"history": session.history}


@app.get("/api/profiles")
def get_profiles(user: dict = Depends(require_auth)):
    return {"profiles": list_profiles()}


@app.get("/api/profiles/{name}")
def get_profile(name: str, user: dict = Depends(require_auth)):
    try:
        config = load_profile(name)
        return _config_to_dict(config)
    except Exception as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/profiles/{name}")
def create_profile_route(name: str, body: dict, user: dict = Depends(require_auth)):
    try:
        config = _config_from_dict(dict(body))
        path = save_profile(config, name)
        return {"ok": True, "path": str(path)}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/profiles/{name}")
def delete_profile_route(name: str, user: dict = Depends(require_auth)):
    from core.config import PROFILES_DIR

    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, "Profile not found")
    path.unlink()
    return {"ok": True}


@app.get("/api/admin/users")
def admin_list_users(
    q: str | None = Query(default=None),
    admin: dict = Depends(require_admin),
):
    rows = search_users(q) if q and q.strip() else list_users()
    return {"users": [_serialize_user(row) for row in rows]}


@app.post("/api/admin/users")
def admin_create_user(body: dict, admin: dict = Depends(require_admin)):
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    quota = _coerce_quota(body.get("quota", 0))
    if not username or not password:
        raise HTTPException(400, "Cần nhập username và password")

    from web.auth import hash_password

    try:
        created = create_user(
            username=username,
            password_hash=hash_password(password),
            role="user",
            quota_remaining=quota,
        )
    except Exception as exc:
        raise HTTPException(400, f"Không tạo được user: {exc}") from exc

    return {"user": _serialize_user(created)}


@app.put("/api/admin/users/{uid}")
def admin_update_user(uid: int, body: dict, admin: dict = Depends(require_admin)):
    updated = update_quota(uid, _coerce_quota(body.get("quota")))
    if not updated:
        raise HTTPException(404, "User not found")
    return {"user": _serialize_user(updated)}


@app.delete("/api/admin/users/{uid}")
def admin_delete_user(uid: int, admin: dict = Depends(require_admin)):
    if uid == admin["id"]:
        raise HTTPException(400, "Không thể tự xóa tài khoản admin đang đăng nhập")
    if not delete_user(uid):
        raise HTTPException(404, "User not found")
    return {"ok": True}
