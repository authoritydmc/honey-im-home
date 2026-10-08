"""Ubuntu-style fake shell. Pure functions + per-session state. No real exec."""
import time
from datetime import datetime

MOTD = (
    "\r\nWelcome to Ubuntu 24.04 LTS (GNU/Linux 6.8.0-41-generic x86_64)\r\n"
    " * Documentation:  https://help.ubuntu.com\r\n"
    " * Management:     https://landscape.canonical.com\r\n"
    " * Support:        https://ubuntu.com/pro\r\n"
)

FAKE_FILES = {
    "/home/ubuntu": ["snap", "Documents", "Downloads", "app", ".bashrc", ".profile"],
    "/var/www": ["html", "config.php"],
    "/etc": ["passwd", "hosts", "hostname"],
}

FAKE_PASSWD = "root:x:0:0:root:/root:/bin/bash\r\nubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash\r\n"

class ShellState:
    def __init__(self, username: str, src_ip: str):
        self.username = username
        self.src_ip = src_ip
        self.cwd = f"/home/{username}" if username else "/home/ubuntu"
        self.awaiting_sudo_pass = False
        self.pending_sudo_cmd = ""

def prompt(st: ShellState) -> str:
    return f"\r\n{st.username}@prod-server:{st.cwd}$ "

def initial_greeting(st: ShellState) -> str:
    login = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    return MOTD + f"\r\nLast login: {login} from {st.src_ip}\r\n" + prompt(st)

def handle_line(st: ShellState, line: str):
    """Returns (output_to_send, command_to_log_or_None, secret_kind)."""
    line = line.strip()
    if not line:
        return prompt(st), None, None
    # sudo password capture
    if st.awaiting_sudo_pass:
        st.awaiting_sudo_pass = False
        out = f"\r\nSorry, user {st.username} is not in the sudoers file. This incident will be reported.\r\n" + prompt(st)
        return out, f"[sudo-password] {line}", "sudo-password"
    parts = line.split()
    cmd = parts[0]
    if cmd == "sudo":
        st.awaiting_sudo_pass = True
        st.pending_sudo_cmd = line
        return f"\r\n[sudo] password for {st.username}: ", line, None
    if cmd in ("wget", "curl"):
        url = parts[-1] if len(parts) > 1 else ""
        return f"\r\n--{datetime.now():%Y-%m-%d %H:%M:%S}--  Connecting... failed: Connection refused.\r\n" + prompt(st), line, "url" if url.startswith("http") else None
    if cmd in ("ssh", "scp"):
        return "\r\nssh: connect to host port 22: Connection timed out\r\n" + prompt(st), line, "lateral"
    if cmd == "whoami":
        return f"\r\n{st.username}\r\n" + prompt(st), line, None
    if cmd == "id":
        return f"\r\nuid=1000({st.username}) gid=1000({st.username}) groups=1000({st.username})\r\n" + prompt(st), line, None
    if cmd == "pwd":
        return f"\r\n{st.cwd}\r\n" + prompt(st), line, None
    if cmd == "hostname":
        return "\r\nprod-server\r\n" + prompt(st), line, None
    if cmd == "uname":
        return "\r\nLinux prod-server 6.8.0-41-generic #41-Ubuntu SMP x86_64 GNU/Linux\r\n" + prompt(st), line, None
    if cmd == "uptime":
        return "\r\n 14:23:17 up 127 days,  3:42,  1 user,  load average: 0.08, 0.03, 0.01\r\n" + prompt(st), line, None
    if cmd == "ls":
        files = FAKE_FILES.get(st.cwd, ["app", "data", ".bashrc"])
        return "\r\n" + "  ".join(files) + "\r\n" + prompt(st), line, None
    if cmd == "cd":
        if len(parts) > 1:
            st.cwd = parts[1] if parts[1].startswith("/") else st.cwd.rstrip("/") + "/" + parts[1]
        else:
            st.cwd = f"/home/{st.username}"
        return prompt(st), line, None
    if cmd == "cat":
        if "shadow" in line:
            return "\r\ncat: /etc/shadow: Permission denied\r\n" + prompt(st), line, None
        if "passwd" in line:
            return "\r\n" + FAKE_PASSWD.replace("\n", "\r\n") + prompt(st), line, None
        return "\r\nNo such file or directory\r\n" + prompt(st), line, None
    if cmd == "ps":
        return "\r\n  PID TTY          TIME CMD\r\n 1234 pts/0    00:00:00 bash\r\n 5678 pts/0    00:00:00 ps\r\n" + prompt(st), line, None
    if cmd in ("ifconfig", "ip"):
        return "\r\neth0: inet 10.0.2.15  netmask 255.255.255.0  broadcast 10.0.2.255\r\n" + prompt(st), line, None
    if cmd == "history":
        return "\r\n    1  cd /var/www\r\n    2  ls -la\r\n    3  cat config.php\r\n" + prompt(st), line, None
    if cmd == "env":
        return f"\r\nUSER={st.username}\r\nHOME=/home/{st.username}\r\nSHELL=/bin/bash\r\n" + prompt(st), line, None
    if cmd in ("exit", "logout"):
        return "\r\nlogout\r\n", line, None
    if cmd == "clear":
        return "\033[2J\033[H" + prompt(st), line, None
    if cmd == "apt":
        time.sleep(0.3)
        return "\r\nE: Unable to acquire the dpkg frontend lock. Are you root?\r\n" + prompt(st), line, None
    return f"\r\nbash: {cmd}: command not found\r\n" + prompt(st), line, None
