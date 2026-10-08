"""SQLite schema + helpers. JSONL in DATA_DIR/events.jsonl is source of truth."""
import json, os, sqlite3, time

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
 id TEXT PRIMARY KEY, started_at REAL, ended_at REAL,
 src_ip TEXT, src_port INTEGER, client_version TEXT,
 kex TEXT, cipher TEXT, geo_country TEXT, geo_city TEXT, asn TEXT, org TEXT, rdns TEXT);
CREATE TABLE IF NOT EXISTS auth_attempts(
 id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, ts REAL,
 username TEXT, password TEXT, key_type TEXT, fingerprint TEXT, key_b64 TEXT,
 method TEXT, success INTEGER);
CREATE TABLE IF NOT EXISTS commands(
 id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, ts REAL,
 username TEXT, cwd TEXT, command TEXT, output_preview TEXT);
CREATE TABLE IF NOT EXISTS tty_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, ts REAL,
 kind TEXT, data TEXT, cols INTEGER, rows INTEGER);
CREATE INDEX IF NOT EXISTS idx_auth_ip ON auth_attempts(username);
CREATE INDEX IF NOT EXISTS idx_sess_ip ON sessions(src_ip);
"""

def data_dir():
    d = os.environ.get("DATA_DIR", "./data")
    os.makedirs(d, exist_ok=True)
    return d

def db_path():
    return os.path.join(data_dir(), "honey.db")

def get_db():
    con = sqlite3.connect(db_path(), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con

DB = None
def db():
    global DB
    if DB is None:
        DB = get_db()
    return DB

def log_jsonl(obj: dict):
    p = os.path.join(data_dir(), "events.jsonl")
    with open(p, "a") as f:
        f.write(json.dumps(obj) + "\n")
