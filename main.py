import os
import hmac
import hashlib
import json
import base64
import sqlite3
import time
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

# ---------- CONFIG ----------
# Railway'da "Variables" bo'limiga qo'shing:
#   BOT_TOKEN   -> @BotFather bergan token
#   SECRET_KEY  -> ixtiyoriy uzun tasodifiy matn (session imzosi uchun)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-railway-variables")
DB_PATH = os.environ.get("DB_PATH", "stepway.db")
SESSION_TTL = 60 * 60 * 24 * 30  # 30 kun

app = FastAPI(title="StepWay API")


# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            username TEXT,
            avg_speed REAL DEFAULT 1.3
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            distance_m REAL NOT NULL,
            duration_sec REAL NOT NULL,
            steps INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ---------- SESSION TOKEN (stdlib only, no JWT dependency) ----------
def make_token(telegram_id: int) -> str:
    expiry = int(time.time()) + SESSION_TTL
    payload = f"{telegram_id}:{expiry}".encode()
    sig = hmac.new(SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload).decode() + "." + sig


def verify_token(token: str) -> int:
    try:
        payload_b64, sig = token.split(".")
        payload = base64.urlsafe_b64decode(payload_b64.encode())
        expected_sig = hmac.new(SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("bad signature")
        telegram_id_str, expiry_str = payload.decode().split(":")
        if int(expiry_str) < time.time():
            raise ValueError("expired")
        return int(telegram_id_str)
    except Exception:
        raise HTTPException(status_code=401, detail="Sessiya yaroqsiz, qayta kiring")


def get_current_user(authorization: Optional[str]) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Kirish talab qilinadi")
    token = authorization.removeprefix("Bearer ").strip()
    telegram_id = verify_token(token)
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Foydalanuvchi topilmadi")
    return user


# ---------- TELEGRAM LOGIN VERIFICATION ----------
def check_telegram_auth(data: dict) -> bool:
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Serverda BOT_TOKEN sozlanmagan")
    received_hash = data.get("hash")
    if not received_hash:
        return False
    check_fields = {k: v for k, v in data.items() if k != "hash"}
    data_check_string = "\n".join(f"{k}={check_fields[k]}" for k in sorted(check_fields))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        return False
    auth_date = int(data.get("auth_date", 0))
    if time.time() - auth_date > 86400:  # 1 kundan eski login rad etiladi
        return False
    return True


class TelegramAuthPayload(BaseModel):
    id: int
    first_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


@app.post("/api/auth/telegram")
def auth_telegram(payload: TelegramAuthPayload):
    data = payload.model_dump(exclude_none=True)
    if not check_telegram_auth(data):
        raise HTTPException(status_code=403, detail="Telegram tasdiqlash muvaffaqiyatsiz")

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (payload.id,)).fetchone()
    if user is None:
        conn.execute(
            "INSERT INTO users (telegram_id, first_name, username) VALUES (?, ?, ?)",
            (payload.id, payload.first_name, payload.username),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (payload.id,)).fetchone()
    conn.close()

    token = make_token(payload.id)
    return {
        "token": token,
        "first_name": user["first_name"],
        "avg_speed": user["avg_speed"],
    }


# ---------- ME ----------
@app.get("/api/me")
def me(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return {"first_name": user["first_name"], "avg_speed": user["avg_speed"]}


# ---------- HISTORY ----------
class HistoryEntry(BaseModel):
    distance_m: float
    duration_sec: float
    steps: int


@app.get("/api/history")
def list_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    conn = get_db()
    rows = conn.execute(
        "SELECT distance_m, duration_sec, steps, created_at FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 50",
        (user["id"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/history")
def add_history(entry: HistoryEntry, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    conn = get_db()

    conn.execute(
        "INSERT INTO history (user_id, distance_m, duration_sec, steps, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
        (user["id"], entry.distance_m, entry.duration_sec, entry.steps),
    )

    # shaxsiy tezlikni yangilash (60% eski, 40% yangi — asta-sekin moslashadi)
    new_speed = entry.distance_m / max(entry.duration_sec, 1)
    blended_speed = (user["avg_speed"] * 0.6) + (new_speed * 0.4)
    conn.execute("UPDATE users SET avg_speed = ? WHERE id = ?", (blended_speed, user["id"]))

    conn.commit()
    conn.close()
    return {"ok": True, "avg_speed": blended_speed}


# ---------- STATIC FRONTEND ----------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
