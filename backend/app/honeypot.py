"""asyncssh honeypot: accept-all password, log keys, full TTY emulation."""
import asyncio, os, time, uuid
import asyncssh
from . import db as dbmod
from .shell import ShellState, handle_line, initial_greeting

BANNER = "SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5"

_SERVERS: dict[int, "HoneyServer"] = {}

def _server_for_process(process) -> "HoneyServer | None":
    try:
        conn = process.get_extra_info("connection")
        if conn is not None:
            return _SERVERS.get(id(conn))
    except Exception:
        pass
    return None

class HoneyServer(asyncssh.SSHServer):
    def __init__(self, src_ip, src_port):
        self.src_ip = src_ip
        self.src_port = src_port
        self.session_id = uuid.uuid4().hex[:12]
        self.username = "ubuntu"
        self.client_version = ""
        self.conn = None

    def connection_made(self, conn):
        self.conn = conn
        _SERVERS[id(conn)] = self
        try:
            peer = conn.get_extra_info("peername")
            if peer:
                self.src_ip, self.src_port = peer[0], peer[1]
            self.client_version = conn.get_extra_info("peer_version", "")
        except Exception:
            pass
        d = dbmod.db()
        d.execute("INSERT INTO sessions(id,started_at,src_ip,src_port,client_version) VALUES(?,?,?,?,?)",
                  (self.session_id, time.time(), self.src_ip, self.src_port, self.client_version))
        d.commit()
        dbmod.log_jsonl({"type": "session.open", "id": self.session_id, "ip": self.src_ip,
                         "port": self.src_port, "client": self.client_version, "ts": time.time()})

    def connection_lost(self, exc):
        try:
            _SERVERS.pop(id(self.conn), None)
        except Exception:
            pass
        try:
            d = dbmod.db()
            d.execute("UPDATE sessions SET ended_at=? WHERE id=?", (time.time(), self.session_id))
            d.commit()
        except Exception:
            pass
        dbmod.log_jsonl({"type": "session.close", "id": self.session_id, "ts": time.time()})

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        self.username = username or "ubuntu"
        d = dbmod.db()
        d.execute("INSERT INTO auth_attempts(session_id,ts,username,password,method,success) VALUES(?,?,?,?,?,?)",
                  (self.session_id, time.time(), username, password, "password", 1))
        d.commit()
        dbmod.log_jsonl({"type": "auth", "id": self.session_id, "ip": self.src_ip,
                         "user": username, "method": "password", "ts": time.time()})
        return True

    def public_key_auth_supported(self):
        return True

    def validate_public_key(self, username, key):
        fp = key.get_fingerprint() if hasattr(key, "get_fingerprint") else ""
        kt = key.get_algorithm() if hasattr(key, "get_algorithm") else "ssh-key"
        try:
            b64 = key.export_public_key().decode() if hasattr(key, "export_public_key") else ""
        except Exception:
            b64 = ""
        d = dbmod.db()
        d.execute("INSERT INTO auth_attempts(session_id,ts,username,key_type,fingerprint,key_b64,method,success) VALUES(?,?,?,?,?,?,?,?)",
                  (self.session_id, time.time(), username, kt, str(fp), b64[:2000], "publickey", 0))
        d.commit()
        dbmod.log_jsonl({"type": "auth", "id": self.session_id, "ip": self.src_ip,
                         "user": username, "method": "publickey", "fp": str(fp)[:64], "ts": time.time()})
        return False  # force password so we capture it too

async def handle_client(process: asyncssh.SSHServerProcess):
    server = _server_for_process(process)
    if server is None:
        try:
            process.stderr.write("internal error\n")
        except Exception:
            pass
        try:
            process.exit(1)
        except Exception:
            pass
        return
    st = ShellState(server.username, server.src_ip)
    # exec (non-interactive: ssh user@host "cmd") — log + fake output, no shell loop
    if process.command:
        cmd = process.command.strip() if isinstance(process.command, str) else process.command.decode().strip()
        try:
            out, logged, _ = handle_line(st, cmd)
            d = dbmod.db()
            d.execute("INSERT INTO commands(session_id,ts,username,cwd,command,output_preview) VALUES(?,?,?,?,?,?)",
                      (server.session_id, time.time(), st.username, st.cwd, (logged or cmd)[:2000], out[:500]))
            d.execute("INSERT INTO tty_events(session_id,ts,kind,data) VALUES(?,?,?,?)",
                      (server.session_id, time.time(), "exec", cmd[:2000]))
            d.commit()
            dbmod.log_jsonl({"type": "cmd", "id": server.session_id, "ip": server.src_ip,
                             "user": st.username, "cmd": (logged or cmd)[:2000], "ts": time.time()})
            process.stdout.write(out)
            await process.stdout.drain()
        except Exception as e:
            import traceback; traceback.print_exc()
            try:
                process.stderr.write(f"honey error: {e}\n")
            except Exception:
                pass
        try:
            process.exit(0)
        except Exception:
            pass
        return
    process.stdout.write(initial_greeting(st))
    buf = ""
    try:
        async for data in process.stdin:
            # log keystroke timing
            d = dbmod.db()
            d.execute("INSERT INTO tty_events(session_id,ts,kind,data) VALUES(?,?,?,?)",
                      (server.session_id, time.time(), "key", data[:500]))
            d.commit()
            for ch in data:
                if ch in ("\r", "\n"):
                    out, cmd, _ = handle_line(st, buf)
                    if cmd:
                        d.execute("INSERT INTO commands(session_id,ts,username,cwd,command,output_preview) VALUES(?,?,?,?,?,?)",
                                  (server.session_id, time.time(), st.username, st.cwd, cmd[:2000], out[:500]))
                        d.commit()
                        dbmod.log_jsonl({"type": "cmd", "id": server.session_id, "ip": server.src_ip,
                                         "user": st.username, "cmd": cmd[:2000], "ts": time.time()})
                    try:
                        process.stdout.write(out)
                    except Exception:
                        return
                    if buf.strip() in ("exit", "logout"):
                        process.exit(0)
                        return
                    buf = ""
                elif ch == "\x7f":
                    buf = buf[:-1]
                    try:
                        process.stdout.write("\b \b")
                    except Exception:
                        pass
                elif ch == "\x03":
                    buf = ""
                    process.stdout.write("^C" + f"\r\n{st.username}@prod-server:{st.cwd}$ ")
                elif ch == "\x04":
                    process.stdout.write("\r\nlogout\r\n")
                    process.exit(0)
                    return
                else:
                    buf += ch
                    try:
                        process.stdout.write(ch)
                    except Exception:
                        pass
    except asyncssh.BreakReceived:
        pass
    except Exception:
        pass

async def start_honeypot(host="0.0.0.0", port=2222):
    keys = None
    kp = os.path.join(dbmod.data_dir(), "ssh_host_key")
    if not os.path.exists(kp):
        k = asyncssh.generate_private_key("ssh-rsa", key_size=2048)
        k.write_private_key(kp)
    await asyncssh.create_server(
        lambda: HoneyServer("?", 0), host, port,
        server_host_keys=[kp],
        server_version=BANNER,
        process_factory=handle_client,
    )
