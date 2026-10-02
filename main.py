"""PocketSmart AI - FastAPI application (routes, sessions, uploads, pages)."""
import asyncio
import json
import logging
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import config as cfg
import database as db
from auth import (active_sessions, blacklisted_tokens, create_access_token, decode_token, get_current_user,
                  get_optional_user, get_token, hash_password, touch_session, verify_password)
from gemini_utils import (ai_enabled, get_home_recommendations, get_jewelry_recommendations,
                          get_party_recommendations)
from models import HomeBudgetInput, JewelryBudgetInput, PartyBudgetInput, RegisterUser

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pocketsmart")


# ----------------------------------------------------------------------------- app setup
async def _cleanup_expired_sessions() -> None:
    while True:
        await asyncio.sleep(300)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=cfg.SESSION_IDLE_MINUTES)
        for name in [n for n, s in active_sessions.items() if s["last_activity"] < cutoff]:
            active_sessions.pop(name, None)
            logger.info("Removed idle session for %s", name)


@asynccontextmanager
async def lifespan(_: FastAPI):
    cfg.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    if cfg.SECRET_KEY_IS_EPHEMERAL:
        logger.warning("SECRET_KEY is not set: using a temporary key, so logins reset on restart.")
    logger.info("Gemini: %s (model %s)", "ENABLED" if ai_enabled() else "DISABLED - demo mode", cfg.GEMINI_MODEL)
    task = asyncio.create_task(_cleanup_expired_sessions())
    yield
    task.cancel()


app = FastAPI(title="PocketSmart: AI Budget Planner", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=cfg.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=cfg.BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(cfg.BASE_DIR / "templates"))
templates.env.globals["year"] = datetime.now().year


def render(request: Request, name: str, user: Optional[dict] = None, **context: Any):
    return templates.TemplateResponse(request, name, {"user": user, "ai_enabled": ai_enabled(), **context})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Browser navigation to a protected page -> redirect to login; API calls -> JSON."""
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


# ----------------------------------------------------------------------------- helpers
def _inr(n: float) -> str:
    n = int(round(n))
    s = str(abs(n))
    if len(s) > 3:
        head, tail, parts = s[:-3], s[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"{'-' if n < 0 else ''}₹{s}"


def _store(user: dict, kind: str, input_data: dict, input_summary: str, result: dict) -> dict:
    summary = f"Planned {_inr(result['allocated'])} of {_inr(result['total_budget'])}, {_inr(result['remaining_budget'])} left"
    result["history_id"] = db.save_history(user["username"], kind, input_data, result, input_summary, summary)
    return result


def _remember(user: dict, key: str, value: dict) -> None:
    touch_session(user["username"])["user_data"][key] = {"timestamp": datetime.now(timezone.utc).isoformat(), **value}


def save_upload(upload: UploadFile) -> Path:
    """Validate and re-encode an uploaded image; the client-supplied filename is never used."""
    data = upload.file.read(cfg.MAX_UPLOAD_BYTES + 1)
    if len(data) > cfg.MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large (max 5 MB)")
    try:
        image = Image.open(BytesIO(data))
        image.load()
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload a valid JPG, PNG or WebP image")
    image.thumbnail((1280, 1280))
    cfg.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = cfg.UPLOAD_DIR / f"{uuid.uuid4().hex}.jpg"
    image.save(path, "JPEG", quality=88)
    return path


# ----------------------------------------------------------------------------- public pages
@app.get("/health")
def health():
    return {"status": "ok", "ai_enabled": ai_enabled(), "model": cfg.GEMINI_MODEL}


@app.get("/")
def index(request: Request):
    return render(request, "index.html", get_optional_user(request), active="home")


@app.get("/login")
def login_page(request: Request):
    if get_optional_user(request):
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    return render(request, "login.html")


@app.get("/register")
def register_page(request: Request):
    if get_optional_user(request):
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    return render(request, "register.html")


# ----------------------------------------------------------------------------- auth API
@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterUser):
    try:
        db.create_user(payload.username, payload.email, payload.full_name, hash_password(payload.password))
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username or email is already registered")
    return {"message": "Account created", "username": payload.username}


@app.post("/token")
def login_for_access_token(form: OAuth2PasswordRequestForm = Depends()):
    ident = form.username.strip().lower()
    user = db.get_user(ident) or db.get_user_by_email(ident)
    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(user["username"])
    active_sessions.pop(user["username"], None)  # fresh session record
    touch_session(user["username"])
    response = JSONResponse({"access_token": token, "token_type": "bearer"})
    response.set_cookie("access_token", token, httponly=True, samesite="lax", secure=cfg.COOKIE_SECURE,
                        max_age=cfg.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return response


@app.api_route("/logout", methods=["GET", "POST"])
def logout(request: Request):
    token = get_token(request)
    if token:
        blacklisted_tokens.add(token)
        username = decode_token(token)
        if username:
            active_sessions.pop(username, None)
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response


@app.get("/session-info")
def session_info(user: dict = Depends(get_current_user)):
    s = active_sessions[user["username"]]
    now = datetime.now(timezone.utc)
    return {
        "username": s["username"],
        "login_time": s["login_time"].isoformat(),
        "last_activity": s["last_activity"].isoformat(),
        "session_duration_minutes": int((now - s["login_time"]).total_seconds() // 60),
        "user_data": s["user_data"],
    }


@app.post("/session-data")
def update_session_data(data: dict[str, Any], user: dict = Depends(get_current_user)):
    if len(json.dumps(data, default=str)) > 10_000:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Session data too large")
    session = touch_session(user["username"])
    session["user_data"].update(data)
    return {"message": "Session data updated", "data": session["user_data"]}


# ----------------------------------------------------------------------------- protected pages
@app.get("/dashboard")
def dashboard(request: Request, user: dict = Depends(get_current_user)):
    return render(request, "dashboard.html", user, active="dashboard")


@app.get("/home-planner")
def home_planner(request: Request, user: dict = Depends(get_current_user)):
    return render(request, "home_planner.html", user, active="home-planner")


@app.get("/party-planner")
def party_planner(request: Request, user: dict = Depends(get_current_user)):
    return render(request, "party_planner.html", user, active="party-planner")


@app.get("/jewelry-planner")
def jewelry_planner(request: Request, user: dict = Depends(get_current_user)):
    return render(request, "jewelry_planner.html", user, active="jewelry-planner")


@app.get("/history")
def history_page(request: Request, user: dict = Depends(get_current_user)):
    return render(request, "history.html", user, active="history")


# ----------------------------------------------------------------------------- planner API
@app.post("/home-budget")
@app.post("/generate-home")
def plan_home_budget(budget_input: HomeBudgetInput, user: dict = Depends(get_current_user)):
    _remember(user, "last_home_budget", {"budget": budget_input.total_budget})
    result = get_home_recommendations(budget_input)
    rooms = ", ".join(n for n, on in (("living room", budget_input.has_living_room),
                                      ("kitchen", budget_input.has_kitchen),
                                      ("bedroom", budget_input.has_bedroom)) if on) or "no rooms selected"
    summary = (f"Budget {_inr(budget_input.total_budget)}; rooms: {rooms}; {budget_input.num_lights} lights, "
               f"{budget_input.num_fans} fans, {budget_input.num_furniture} furniture, "
               f"{budget_input.num_dining_tables} dining tables")
    return _store(user, "home", budget_input.model_dump(), summary, result)


@app.post("/party-budget")
@app.post("/generate-party")
def plan_party_budget(budget_input: PartyBudgetInput, user: dict = Depends(get_current_user)):
    _remember(user, "last_party_budget", {"budget": budget_input.total_budget, "guests": budget_input.num_guests})
    result = get_party_recommendations(budget_input)
    summary = (f"Budget {_inr(budget_input.total_budget)}; {budget_input.party_type} for "
               f"{budget_input.num_guests} guests at {budget_input.venue_type or 'unspecified venue'}")
    return _store(user, "party", budget_input.model_dump(), summary, result)


@app.post("/jewelry-budget")
@app.post("/generate-jewelry")
def plan_jewelry_budget(
    total_budget: float = Form(..., gt=0),
    occasion: str = Form(..., min_length=2, max_length=60),
    preferences: Optional[str] = Form(None, max_length=500),
    image: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
):
    try:
        budget_input = JewelryBudgetInput(total_budget=total_budget, occasion=occasion, preferences=preferences)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.errors(include_url=False, include_context=False))
    has_image = bool(image and image.filename)
    image_path = save_upload(image) if has_image else None
    _remember(user, "last_jewelry_budget", {"budget": total_budget, "occasion": occasion, "has_image": has_image})
    try:
        result = get_jewelry_recommendations(budget_input, str(image_path) if image_path else None)
    finally:
        if image_path and not cfg.KEEP_UPLOADS:
            image_path.unlink(missing_ok=True)
    input_data = {**budget_input.model_dump(), "has_image": has_image}
    summary = (f"Budget {_inr(total_budget)}; occasion: {occasion}; "
               f"outfit image: {'yes' if has_image else 'no'}")
    return _store(user, "jewelry", input_data, summary, result)


# ----------------------------------------------------------------------------- history API
@app.get("/recommendation-history")
def recommendation_history(limit: int = Query(50, ge=1, le=200), user: dict = Depends(get_current_user)):
    rows = db.list_history(user["username"], limit)
    return {"history": [{
        "id": r["id"], "timestamp": r["created_at"], "type": r["rec_type"], "input": r["input_summary"],
        "summary": r["result_summary"], "input_data": r["input_data"],
        "total_budget": r["total_budget"], "remaining_budget": r["remaining_budget"],
    } for r in rows]}


@app.get("/recommendation-details/{recommendation_id}")
def recommendation_details(recommendation_id: str, user: dict = Depends(get_current_user)):
    item = db.get_history_item(user["username"], recommendation_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found")
    return {"id": item["id"], "timestamp": item["created_at"], "type": item["rec_type"],
            "input": item["input_summary"], "input_data": item["input_data"], "full_result": item["full_result"]}


if __name__ == "__main__":
    import uvicorn

    print("Starting PocketSmart: AI Budget Planner ...")
    uvicorn.run("main:app", host=cfg.HOST, port=cfg.PORT, reload=True)
