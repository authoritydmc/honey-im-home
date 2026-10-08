"""FastAPI: auth + stats + sessions/attackers + live WS + serves React dist."""
import asyncio, os, time
from fastapi import FastAPI, Depends, HTTPException, WebSocket, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from passlib.context import CryptContext

from . import db as dbmod
from .honeypot import start_honeypot

SECRET = os.environ.get("SECRET_KEY", "dev-secret-change-me-32-chars!!")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")
API_PORT = int(os.environ.get("API_PORT", "8078"))
HONEY_HOST = os.environ.get("HONEYPOT_HOST", "0.0.0.0")
HONEY_PORT = int(os.environ.get("HONEYPOT_PORT", "2222"))

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
ADMIN_HASH = pwd.hash(ADMIN_PASSWORD)
security = HTTPBearer(auto_error=False)

app = FastAPI(title="Honey I'm Home API")
live_queues: set[asyncio.Queue] = set()

def make_token(role="admin"):
    return jwt.encode({"sub": role, "exp": time.time() + 12 * 3600}, SECRET, algorithm="HS256")

def require_auth(request: Request, cred: HTTPAuthorizationCredentials = Depends(security)):
    # Traefik+Authentik SSO: trust X-Forwarded-User, but that header only
    # arrives via the forwardAuth middleware (API binds 127.0.0.1, so direct
    # callers cannot spoof it from outside the box).
    if os.environ.get("TRUST_PROXY_AUTH") == "1" and request.headers.get("X-Forwarded-User"):
        return "admin"
    if not cred:
        raise HTTPException(401, "login required")
    try:
        jwt.decode(cred.credentials, SECRET, algorithms=["HS256"])
        return "admin"
    except Exception:
        raise HTTPException(401, "bad token")

@app.on_event("startup")
async def _startup():
    dbmod.db()
    asyncio.create_task(start_honeypot(HONEY_HOST, HONEY_PORT))

@app.get("/healthz")
def healthz():
    return {"ok": True, "ts": time.time()}

@app.post("/api/auth/login")
def login(body: dict):
    if not pwd.verify(body.get("password", ""), ADMIN_HASH):
        raise HTTPException(401, "bad password")
    return {"token": make_token()}

@app.get("/api/stats")
def stats(_=Depends(require_auth)):
    d = dbmod.db()
    s = d.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
    a = d.execute("SELECT COUNT(*) c FROM auth_attempts").fetchone()["c"]
    c = d.execute("SELECT COUNT(*) c FROM commands").fetchone()["c"]
    ips = d.execute("SELECT COUNT(DISTINCT src_ip) c FROM sessions").fetchone()["c"]
    top_ips = [dict(r) for r in d.execute(
        "SELECT src_ip, COUNT(*) n FROM sessions GROUP BY src_ip ORDER BY n DESC LIMIT 10")]
    top_users = [dict(r) for r in d.execute(
        "SELECT username, COUNT(*) n FROM auth_attempts GROUP BY username ORDER BY n DESC LIMIT 10")]
    timeline = [dict(r) for r in d.execute(
        "SELECT CAST(ts/3600 AS INT)*3600 h, COUNT(*) n FROM auth_attempts WHERE ts > ? GROUP BY h ORDER BY h",
        (time.time() - 48 * 3600,))]
    return {"sessions": s, "auths": a, "commands": c, "ips": ips,
            "top_ips": top_ips, "top_users": top_users, "timeline": timeline}

@app.get("/api/sessions")
def sessions(ip: str = "", limit: int = 50, _=Depends(require_auth)):
    d = dbmod.db()
    q = "SELECT * FROM sessions WHERE (?='' OR src_ip=?) ORDER BY started_at DESC LIMIT ?"
    return [dict(r) for r in d.execute(q, (ip, ip, limit))]

@app.get("/api/credentials")
def creds(limit: int = 100, _=Depends(require_auth)):
    d = dbmod.db()
    return [dict(r) for r in d.execute(
        "SELECT * FROM auth_attempts ORDER BY ts DESC LIMIT ?", (limit,))]

@app.get("/api/commands")
def cmds(limit: int = 100, _=Depends(require_auth)):
    d = dbmod.db()
    return [dict(r) for r in d.execute(
        "SELECT * FROM commands ORDER BY ts DESC LIMIT ?", (limit,))]

@app.get("/api/attackers")
def attackers(_=Depends(require_auth)):
    d = dbmod.db()
    rows = d.execute("""SELECT s.src_ip AS ip, COUNT(DISTINCT s.id) sessions,
      COUNT(a.id) attempts, MIN(a.ts) first_seen, MAX(a.ts) last_seen,
      GROUP_CONCAT(DISTINCT a.username) users
      FROM sessions s LEFT JOIN auth_attempts a ON a.session_id=s.id
      GROUP BY s.src_ip ORDER BY attempts DESC LIMIT 100""").fetchall()
    return [dict(r) for r in rows]

@app.websocket("/api/live")
async def live(ws: WebSocket):
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue()
    live_queues.add(q)
    try:
        while True:
            msg = await q.get()
            await ws.send_json(msg)
    except Exception:
        pass
    finally:
        live_queues.discard(q)

# serve React build if present
DIST = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(DIST):
    app.mount("/honey", StaticFiles(directory=DIST, html=True), name="ui")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
