"""Storage backend: SQLite (default) or Postgres (DATABASE_URL=postgresql://...).

Schema is kept identical across dialects. Retention purge + JSONL rotation
keep disk bounded (RETENTION_DAYS, JSONL_MAX_MB, MAX_DB_GB).
"""
import json
import os
import time

RETENTION_DAYS = float(os.environ.get("RETENTION_DAYS", "2"))
JSONL_MAX_MB = float(os.environ.get("JSONL_MAX_MB", "100"))
JSONL_KEEP = int(os.environ.get("JSONL_KEEP", "3"))
MAX_DB_GB = float(os.environ.get("MAX_DB_GB", "10"))

SCHEMA_SQLITE = """
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
CREATE INDEX IF NOT EXISTS idx_auth_ts ON auth_attempts(ts);
CREATE INDEX IF NOT EXISTS idx_cmd_ts ON commands(ts);
CREATE INDEX IF NOT EXISTS idx_sess_ip ON sessions(src_ip);
CREATE INDEX IF NOT EXISTS idx_sess_ts ON sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_tty_ts ON tty_events(ts);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS sessions(
 id TEXT PRIMARY KEY, started_at DOUBLE PRECISION, ended_at DOUBLE PRECISION,
 src_ip TEXT, src_port INTEGER, client_version TEXT,
 kex TEXT, cipher TEXT, geo_country TEXT, geo_city TEXT, asn TEXT, org TEXT, rdns TEXT);
CREATE TABLE IF NOT EXISTS auth_attempts(
 id SERIAL PRIMARY KEY, session_id TEXT, ts DOUBLE PRECISION,
 username TEXT, password TEXT, key_type TEXT, fingerprint TEXT, key_b64 TEXT,
 method TEXT, success INTEGER);
CREATE TABLE IF NOT EXISTS commands(
 id SERIAL PRIMARY KEY, session_id TEXT, ts DOUBLE PRECISION,
 username TEXT, cwd TEXT, command TEXT, output_preview TEXT);
CREATE TABLE IF NOT EXISTS tty_events(
 id SERIAL PRIMARY KEY, session_id TEXT, ts DOUBLE PRECISION,
 kind TEXT, data TEXT, cols INTEGER, rows INTEGER);
CREATE INDEX IF NOT EXISTS idx_auth_ip ON auth_attempts(username);
CREATE INDEX IF NOT EXISTS idx_auth_ts ON auth_attempts(ts);
CREATE INDEX IF NOT EXISTS idx_cmd_ts ON commands(ts);
CREATE INDEX IF NOT EXISTS idx_sess_ip ON sessions(src_ip);
CREATE INDEX IF NOT EXISTS idx_sess_ts ON sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_tty_ts ON tty_events(ts);
"""

# Backwards compat for old import
SCHEMA = SCHEMA_SQLITE


def data_dir():
    d = os.environ.get("DATA_DIR", "./data")
    os.makedirs(d, exist_ok=True)
    return d


def db_path():
    return os.path.join(data_dir(), "honey.db")


def use_postgres():
    return os.environ.get("DATABASE_URL", "").startswith(("postgres://", "postgresql://"))


def get_db():
    if use_postgres():
        import psycopg2
        import psycopg2.extras

        con = psycopg2.connect(os.environ["DATABASE_URL"])
        con.autocommit = True
        with con.cursor() as cur:
            cur.execute(SCHEMA_PG)
        # adapt sqlite-style Row access: RealDictCursor per query is handled
        # by thin wrapper below
        return _PgWrap(con)
    import sqlite3

    con = sqlite3.connect(db_path(), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_SQLITE)
    # bound growth: cap freelist reuse
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    return con


class _PgWrap:
    """Minimal sqlite3-compatible facade over a psycopg2 connection.

    Translates '?' placeholders to '%s' and returns dict-like rows.
    """

    def __init__(self, con):
        self._con = con

    def execute(self, sql, params=()):
        import psycopg2.extras

        cur = self._con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql.replace("?", "%s"), tuple(params))
        # psycopg2 cursors are iterable; stash for fetchall/fetchone
        return _PgCur(cur)

    def executescript(self, sql):
        with self._con.cursor() as cur:
            cur.execute(sql)

    def commit(self):
        pass  # autocommit on

    def close(self):
        self._con.close()


class _PgCur:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur.fetchall())


DB = None


def db():
    global DB
    if DB is None:
        DB = get_db()
    return DB


def _jsonl_path():
    return os.path.join(data_dir(), "events.jsonl")


def log_jsonl(obj: dict):
    """Append with size-based rotation: events.jsonl -> .1, .2 (keep JSONL_KEEP)."""
    p = _jsonl_path()
    try:
        if os.path.exists(p) and os.path.getsize(p) > JSONL_MAX_MB * 1024 * 1024:
            for i in range(JSONL_KEEP - 1, 0, -1):
                src = f"{p}.{i}" if i else p
                dst = f"{p}.{i + 1}"
                try:
                    if os.path.exists(src):
                        os.replace(src, dst)
                except Exception:
                    pass
            try:
                if os.path.exists(f"{p}.{JSONL_KEEP}"):
                    os.remove(f"{p}.{JSONL_KEEP}")
            except Exception:
                pass
    except Exception:
        pass
    with open(p, "a") as f:
        f.write(json.dumps(obj) + "\n")


def storage_stats():
    """Disk usage of honey data (sqlite file + jsonl set), bytes."""
    total = 0
    try:
        base = data_dir()
        for name in os.listdir(base):
            if name == "ssh_host_key":
                continue
            try:
                total += os.path.getsize(os.path.join(base, name))
            except Exception:
                pass
    except Exception:
        pass
    return {"bytes": total, "gb": round(total / 1e9, 3),
            "cap_gb": MAX_DB_GB, "retention_days": RETENTION_DAYS}


def purge_old():
    """Delete rows older than RETENTION_DAYS; enforce MAX_DB_GB cap.

    Returns dict of deleted counts. Safe to call periodically.
    """
    cutoff = time.time() - RETENTION_DAYS * 86400
    d = db()
    out = {}
    try:
        for tbl, col in (("tty_events", "ts"), ("auth_attempts", "ts"),
                         ("commands", "ts"), ("sessions", "started_at")):
            try:
                cur = d.execute(f"DELETE FROM {tbl} WHERE {col} < ?", (cutoff,))
                out[tbl] = getattr(cur, "rowcount", None)
            except Exception:
                # _PgCur wraps RealDictCursor which has rowcount on inner
                try:
                    out[tbl] = cur._cur.rowcount
                except Exception:
                    out[tbl] = -1
        try:
            d.commit()
        except Exception:
            pass
        if not use_postgres():
            # hard cap: if sqlite file still > MAX_DB_GB, drop oldest tty first
            try:
                size = os.path.getsize(db_path())
                if size > MAX_DB_GB * 1e9:
                    d.execute("DELETE FROM tty_events WHERE id IN "
                              "(SELECT id FROM tty_events ORDER BY ts ASC LIMIT 50000)")
                    d.execute("DELETE FROM auth_attempts WHERE ts < ?",
                              (time.time() - 86400,))
                    d.commit()
                    out["emergency_trim"] = True
            except Exception:
                pass
            try:
                d.execute("VACUUM")
            except Exception:
                pass
        # trim rotated jsonl beyond keep count
        p = _jsonl_path()
        for i in range(JSONL_KEEP + 1, JSONL_KEEP + 5):
            try:
                os.remove(f"{p}.{i}")
            except Exception:
                pass
    except Exception as e:
        out["error"] = str(e)
    return out
