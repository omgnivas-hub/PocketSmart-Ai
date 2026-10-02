"""Password hashing, JWT handling and the current-user dependency."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request, status

import config as cfg
import database as db

# In-memory state (single-process demo). Swap for Redis/DB if you deploy multiple workers.
blacklisted_tokens: set[str] = set()
active_sessions: dict[str, dict] = {}


def _prepare(password: str) -> bytes:
    # SHA-256 first so passwords of any length work (bcrypt ignores/rejects bytes beyond 72).
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=cfg.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, cfg.SECRET_KEY, algorithm=cfg.ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, cfg.SECRET_KEY, algorithms=[cfg.ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def get_token(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:].strip()
    return token or None


def touch_session(username: str) -> dict:
    now = datetime.now(timezone.utc)
    session = active_sessions.setdefault(
        username, {"username": username, "login_time": now, "last_activity": now, "user_data": {}}
    )
    session["last_activity"] = now
    return session


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: returns the signed-in user or raises 401."""
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    token = get_token(request)
    if not token or token in blacklisted_tokens:
        raise unauthorized
    username = decode_token(token)
    user = db.get_user(username) if username else None
    if not user:
        raise unauthorized
    touch_session(username)
    return {"username": user["username"], "email": user["email"], "full_name": user["full_name"]}


def get_optional_user(request: Request) -> Optional[dict]:
    try:
        return get_current_user(request)
    except HTTPException:
        return None
