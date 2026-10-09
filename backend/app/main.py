"""FastAPI: auth + stats + sessions/attackers + live WS + serves React dist."""
import asyncio, os, time
from fastapi import FastAPI, Depends, HTTPException, WebSocket, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from passlib.context import CryptContext

from . import db as dbmod
from . import intent as intentmod
from .honeypot import start_honeypot

SECRET = os.environ.get("SECRET_KEY", "dev-secret-change-me-32-chars!!")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
API_PORT = int(os.environ.get("API_PORT", "8078"))
HONEY_HOST = os.environ.get("HONEYPOT_HOST", "0.0.0.0")
HONEY_PORT = int(os.environ.get("HONEYPOT_PORT", "2222"))
SSO_ONLY = os.environ.get("SSO_ONLY", "1") == "1"  # default: SSO-only, no password login
AUTH_URL = os.environ.get("AUTH_URL", "https://auth.rajlabs.in")

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
ADMIN_HASH = pwd.hash(ADMIN_PASSWORD) if ADMIN_PASSWORD else None
security = HTTPBearer(auto_error=False)

app = FastAPI(title="Honey I'm Home API")
live_queues: set[asyncio.Queue] = set()

def make_token(role="admin"):
    return jwt.encode({"sub": role, "exp": time.time() + 12 * 3600}, SECRET, algorithm="HS256")

PROXY_USER_HEADERS = ("X-authentik-username", "X-authentik-email", "X-authentik-name",
                        "X-Forwarded-User", "X-Forwarded-Email", "X-Forwarded-Preferred-Username",
                        "Remote-User", "Remote-Email", "Cf-Access-Authenticated-User-Email")
SSO_ONLY = os.environ.get("SSO_ONLY", "0") == "1"


def proxy_user(request: Request):
    if os.environ.get("TRUST_PROXY_AUTH") != "1":
        return None
    for h in PROXY_USER_HEADERS:
        v = (request.headers.get(h) or "").strip()
        if v:
            return v
    return None


def require_auth(request: Request, cred: HTTPAuthorizationCredentials = Depends(security)):
    # Edge SSO (Traefik ForwardAuth / Authelia / Cloudflare Access): trust the
    # identity header the edge injects. The API binds 127.0.0.1 behind the
    # edge, so direct callers cannot spoof it from outside the box.
    # Without the edge, a JWT from /api/auth/login is required.
    if proxy_user(request):
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
    asyncio.create_task(_purge_loop())


async def _purge_loop():
    await asyncio.sleep(60)
    while True:
        try:
            await asyncio.to_thread(dbmod.purge_old)
        except Exception:
            pass
        await asyncio.sleep(3600)

@app.get("/healthz")
def healthz():
    return {"ok": True, "ts": time.time()}

@app.get("/api/auth")
def auth_status(request: Request):
    u = proxy_user(request)
    if u:
        return {"mode": "sso", "login": "sso", "user": u}
    if SSO_ONLY:
        return {"mode": "sso", "login": "sso", "user": None,
                "auth_url": AUTH_URL,
                "hint": "Sign in via RajLabs SSO — no app password."}
    return {"mode": "token", "login": "password", "user": None}


@app.post("/api/auth/login")
def login(body: dict):
    if SSO_ONLY or not ADMIN_HASH:
        # Real SSO sign-in happens at the edge (Traefik ForwardAuth ->
        # Authentik). There is intentionally no password form any more.
        raise HTTPException(403, "password login disabled: use SSO sign-in")
    if not pwd.verify(body.get("password", ""), ADMIN_HASH):
        raise HTTPException(401, "bad password")
    return {"token": make_token()}


@app.get("/api/storage")
def storage(_=Depends(require_auth)):
    return {**dbmod.storage_stats(), "db": "postgres" if dbmod.use_postgres() else "sqlite"}


@app.get("/api/insights")
def insights(limit: int = 500, _=Depends(require_auth)):
    """What attackers tried to do: classified command intents + notes."""
    d = dbmod.db()
    rows = d.execute("SELECT command FROM commands ORDER BY ts DESC LIMIT ?", (limit,))
    cmds = [r["command"] if isinstance(r, dict) else r[0] for r in rows]
    cards = intentmod.summarize(cmds)
    return {"total": len(cmds), "intents": cards,
            "profile": {"note": "Attackers see a 32-vCPU / 96GB RAM / NVIDIA A100 box "
                                "with 36d uptime — juicy enough to mine on, fake enough to be safe."}}

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
def creds(limit: int = 100, session_id: str = "", ip: str = "", _=Depends(require_auth)):
    d = dbmod.db()
    if ip:
        rows = d.execute(
            """SELECT a.*, s.src_ip AS ip FROM auth_attempts a JOIN sessions s
               ON s.id=a.session_id WHERE s.src_ip=? ORDER BY a.ts DESC LIMIT ?""",
            (ip, limit))
    elif session_id:
        rows = d.execute(
            """SELECT a.*, s.src_ip AS ip FROM auth_attempts a JOIN sessions s
               ON s.id=a.session_id WHERE a.session_id=? ORDER BY a.ts LIMIT ?""",
            (session_id, limit))
    else:
        rows = d.execute(
            """SELECT a.*, s.src_ip AS ip FROM auth_attempts a LEFT JOIN sessions s
               ON s.id=a.session_id ORDER BY a.ts DESC LIMIT ?""", (limit,))
    return [dict(r) for r in rows]

@app.get("/api/commands")
def cmds(limit: int = 100, session_id: str = "", ip: str = "", _=Depends(require_auth)):
    d = dbmod.db()
    if ip:
        rows = d.execute(
            """SELECT c.*, s.src_ip AS ip FROM commands c JOIN sessions s
               ON s.id=c.session_id WHERE s.src_ip=? ORDER BY c.ts DESC LIMIT ?""",
            (ip, limit))
    elif session_id:
        rows = d.execute(
            """SELECT c.*, s.src_ip AS ip FROM commands c JOIN sessions s
               ON s.id=c.session_id WHERE c.session_id=? ORDER BY c.ts LIMIT ?""",
            (session_id, limit))
    else:
        rows = d.execute(
            """SELECT c.*, s.src_ip AS ip FROM commands c LEFT JOIN sessions s
               ON s.id=c.session_id ORDER BY c.ts DESC LIMIT ?""", (limit,))
    return [dict(r) for r in rows]

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

# serve React build if present (root path; API routes take precedence)
DIST = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(DIST):
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
