from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from passlib.hash import bcrypt

SECRET = os.environ.get("JWT_SECRET", "changeme")
ALGORITHM = "HS256"
TOKEN_TTL_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.verify(password, password_hash)
    except Exception:
        return False


def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(401, "Token không hợp lệ hoặc đã hết hạn") from exc

    subject = payload.get("sub")
    username = payload.get("username")
    role = payload.get("role")
    if not subject or not username or not role:
        raise HTTPException(401, "Token thiếu dữ liệu bắt buộc")

    return {"id": int(subject), "username": username, "role": role}


async def require_auth(authorization: str | None = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(401, "Thiếu Authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(401, "Authorization header không đúng định dạng Bearer")

    return verify_token(parts[1].strip())


async def require_admin(user: dict = Depends(require_auth)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Chỉ admin mới được dùng tính năng này")
    return user
