"""Ubuntu-style fake shell. Pure functions + per-session state. No real exec."""
from datetime import datetime

MOTD = (
    "\r\nWelcome to Ubuntu 24.04.1 LTS (GNU/Linux 6.8.0-41-generic x86_64)\r\n"
    " * Documentation:  https://help.ubuntu.com\r\n"
    " * Management:     https://landscape.canonical.com\r\n"
    " * Support:        https://ubuntu.com/pro\r\n"
)

FAKE_FILES = {
    "/home/ubuntu": ["snap", "Documents", "Downloads", "app", ".bashrc", ".profile", ".bash_history"],
    "/var/www": ["html", "config.php"],
    "/var/www/html": ["index.html", "config.php"],
    "/tmp": ["systemd-private-abc123", "snap-private-tmp"],
    "/etc": ["passwd", "hosts", "hostname", "os-release", "ssh"],
}

FAKE_PASSWD = "root:x:0:0:root:/root:/bin/bash\r\nubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash\r\n"

FAKE_SHADOW = (
    "root:!:20156:0:99999:7:::\r\n"
    "ubuntu:!:20156:0:99999:7:::\r\n"
)

FAKE_HOSTS = "127.0.0.1 localhost\r\n127.0.1.1 honey\r\n"

FAKE_CONFIG_PHP = (
    "<?php\r\n// app config -- do not commit\r\n"
    "define('DB_HOST', '127.0.0.1');\r\n"
    "define('DB_USER', 'app_prod');\r\n"
    "define('DB_PASS', 'S3cBr0wnF0x!2024');\r\n"
    "define('DB_NAME', 'shop_production');\r\n"
)

FAKE_BASHRC = (
    "# ~/.bashrc: executed by bash(1) for non-login shells.\r\n"
    "export PATH=\"$HOME/.local/bin:$PATH\"\r\n"
    "alias ll='ls -alF'\r\n"
)

# --- Juicy-but-plausible cloud GPU box: 32 vCPU, 96GB RAM, 1x A100 40GB ---
# Values below are LIVE: uptime ticks from a fixed boot 36 days ago, load and
# GPU telemetry drift with time, so repeated probes look like a real system.
import time as _time
import random as _random

NCPU = 32
MEM_MB = 96483  # ~96GB as reported by free -m
BOOT_TS = _time.time() - 36 * 86400  # booted 36 days ago, keeps ticking


def _uptime_sec():
    return max(0, _time.time() - BOOT_TS)


def _tick(seed_key: str, lo: float, hi: float, n: int = 1):
    """Slowly-drifting pseudo telemetry, stable within a minute."""
    bucket = int(_time.time() // 60)
    rng = _random.Random(f"{seed_key}-{bucket}")
    return [rng.uniform(lo, hi) for _ in range(n)]


def _loadavg():
    l1, l5, l15 = _tick("load", 0.15, 0.45, 3)
    return f"{l1:.2f}, {l5:.2f}, {l15:.2f}"


def _uptime_clock():
    s = int(_uptime_sec())
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    return f"{d} days, {h}:{m:02d}"

FAKE_CPUINFO = "".join(
    f"processor\t: {i}\r\nvendor_id\t: GenuineIntel\r\n"
    f"cpu family\t: 6\r\nmodel\t\t: 143\r\n"
    f"model name\t: Intel(R) Xeon(R) Platinum 8488C\r\n"
    f"cpu MHz\t\t: 2992.969\r\ncache size\t: 107520 KB\r\n"
    f"flags\t\t: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ss ht syscall nx pdpe1gb rdtscp lm constant_tsc\r\n"
    f"bogomips\t: 5985.93\r\n\r\n"
    for i in range(NCPU)
)

FAKE_MEMINFO = (
    "MemTotal:       98810880 kB\r\nMemFree:        71234560 kB\r\n"
    "MemAvailable:   88200192 kB\r\nBuffers:          812032 kB\r\n"
    "Cached:         14212352 kB\r\nSwapTotal:             0 kB\r\n"
    "SwapFree:                0 kB\r\n"
)

FAKE_UPTIME = None  # computed live via _fake_uptime()


def _fake_uptime():
    u = _uptime_sec()
    return f"{u:.2f} {u * 31:.2f}"

FAKE_OS_RELEASE = (
    'NAME="Ubuntu"\r\nVERSION="24.04.1 LTS (Noble Numbat)"\r\nID=ubuntu\r\n'
    'ID_LIKE=debian\r\nPRETTY_NAME="Ubuntu 24.04.1 LTS"\r\nVERSION_ID="24.04"\r\n'
    'HOME_URL="https://www.ubuntu.com/"\r\n'
)

LSPCI = (
    "00:00.0 Host bridge: Intel Corporation 440FX - 82441FX PMC [Natoma]\r\n"
    "00:01.0 ISA bridge: Intel Corporation 82371SB PIIX3 ISA [Natoma/Triton II]\r\n"
    "00:03.0 VGA compatible controller: Amazon.com, Inc. NVMe SSD Controller\r\n"
    "00:1e.0 VGA compatible controller: Cirrus Logic GD 5446\r\n"
    "00:1f.0 3D controller: NVIDIA Corporation GA100 [A100 PCIe 40GB] (rev a1)\r\n"
)

def _nvidia_smi():
    temp = int(_tick("gpu-temp", 33, 38)[0])
    watts = int(_tick("gpu-watts", 68, 76)[0])
    return (
        "+-----------------------------------------------------------------------------+\r\n"
        "| NVIDIA-SMI 550.54.15    Driver Version: 550.54.15    CUDA Version: 12.4     |\r\n"
        "|-------------------------------+----------------------+----------------------+\r\n"
        "|   0  NVIDIA A100 40GB      On   | 00000000:00:1F.0 Off |                    0 |\r\n"
        f"| N/A   {temp}C    P0             {watts}W /  250W |      0MiB /  40960MiB |      0%      Default |\r\n"
        "+-----------------------------------------------------------------------------+\r\n"
    )


NVIDIA_SMI = ""  # computed live via _nvidia_smi()

UNAME_V = "#41-Ubuntu SMP PREEMPT_DYNAMIC Thu Aug  1 16:25:12 UTC 2026"

LS_LONG = (
    "total 32\r\n"
    "drwxr-xr-x 5 ubuntu ubuntu 4096 Oct  4 09:12 .\r\n"
    "drwxr-xr-x 3 root   root   4096 Sep  3 07:55 ..\r\n"
    "-rw------- 1 ubuntu ubuntu  421 Oct  8 11:02 .bash_history\r\n"
    "-rw-r--r-- 1 ubuntu ubuntu  220 Feb 13  2026 .bash_logout\r\n"
    "-rw-r--r-- 1 ubuntu ubuntu 3771 Feb 13  2026 .bashrc\r\n"
    "drwx------ 2 ubuntu ubuntu 4096 Oct  4 10:02 .cache\r\n"
    "-rw-r--r-- 1 ubuntu ubuntu  807 Feb 13  2026 .profile\r\n"
    "drwxr-xr-x 2 ubuntu ubuntu 4096 Aug 17 15:41 Documents\r\n"
    "drwxr-xr-x 2 ubuntu ubuntu 4096 Aug 17 15:41 Downloads\r\n"
    "drwxr-xr-x 2 ubuntu ubuntu 4096 Oct  4 09:53 app\r\n"
    "drwx------ 2 ubuntu ubuntu 4096 Sep  5 20:27 snap\r\n"
)

PS_AUX = (
    "USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\r\n"
    "root           1  0.0  0.1 225360  9132 ?        Ss   Oct04   0:02 /sbin/init\r\n"
    "root         412  0.0  0.0  22012  5100 ?        Ss   Oct04   0:00 /lib/systemd/systemd-journald\r\n"
    "root         587  0.0  0.0  14116  3100 ?        Ss   Oct04   0:01 /usr/sbin/cron -f\r\n"
    "root         701  0.0  0.1  16820  7200 ?        Ss   Oct04   0:03 /usr/sbin/sshd -D\r\n"
    "www-data     812  0.0  0.4  41200 18200 ?        S    Oct04   0:11 /usr/sbin/apache2 -k start\r\n"
    "ubuntu      1240  0.0  0.0  22200  5300 pts/0    Ss   11:02   0:00 -bash\r\n"
)

def _top_snap():
    idle = _tick("cpu-idle", 97.5, 99.2)[0]
    us = 100 - idle - 0.6
    free = int(_tick("mem-free", 69500, 71200)[0])
    used = int(_tick("mem-used", 7800, 8500)[0])
    return (
        f"top - {datetime.now().strftime('%H:%M:%S')} up {_uptime_clock()},  1 user,  load average: {_loadavg()}\r\n"
        "Tasks: 418 total,   1 running, 417 sleeping,   0 stopped,   0 zombie\r\n"
        f"%Cpu(s):  {us:.1f} us,  0.4 sy,  0.0 ni, {idle:.1f} id,  0.0 wa,  0.0 hi,  0.1 si\r\n"
        f"MiB Mem :  96483.0 total,  {free:.1f} free,     {used:.1f} used,   18245.8 buff/cache\r\n"
        "    PID USER      PR  NI    VIRT    RES  %CPU  %MEM     TIME+ COMMAND\r\n"
        "    812 www-data  20   0   41200  18200   1.2   0.0   0:11.32 apache2\r\n"
    )


TOP_SNAP = ""  # computed live via _top_snap()

SS_LISTEN = (
    "State  Recv-Q Send-Q  Local Address:Port   Peer Address:Port\r\n"
    "LISTEN 0      4096        127.0.0.1:3306        0.0.0.0:*\r\n"
    "LISTEN 0      128           0.0.0.0:80          0.0.0.0:*\r\n"
    "LISTEN 0      128           0.0.0.0:22          0.0.0.0:*\r\n"
    "LISTEN 0      128              [::]:80             [::]:*\r\n"
)

DF_H = (
    "Filesystem      Size  Used Avail Use% Mounted on\r\n"
    "/dev/nvme0n1p1  197G   38G  150G  21% /\r\n"
    "tmpfs            48G     0   48G   0% /dev/shm\r\n"
)

FREE_M = (
    "               total        used        free      shared  buff/cache   available\r\n"
    "Mem:           96483        8124       70112         212        18245       86120\r\n"
    "Swap:              0           0           0\r\n"
)

FREE_G = (
    "               total        used        free      shared  buff/cache   available\r\n"
    "Mem:              94           7          68           0          17          84\r\n"
    "Swap:              0           0           0\r\n"
)

LSCPU_SHORT = (
    "Architecture:             x86_64\r\n"
    "  CPU(s):                 32\r\n"
    "  On-line CPU(s) list:    0-31\r\n"
    "  Model name:             Intel(R) Xeon(R) Platinum 8488C\r\n"
    "  CPU MHz:                2992.969\r\n"
)

LSBLK = (
    "NAME   MAJ:MIN RM SIZE RO TYPE MOUNTPOINTS\r\n"
    "sda      8:0    0  50G  0 disk\r\n"
    "└─sda1   8:1    0  50G  0 part /\r\n"
)

LAST_SHORT = (
    "ubuntu   pts/0        203.0.113.44     Tue Oct  7 11:02   still logged in\r\n"
    "reboot   system boot  6.8.0-41-generic Tue Sep  3 07:55   still running\r\n"
)

def _w_short():
    return (f" {datetime.now().strftime('%H:%M:%S')} up {_uptime_clock()},  1 user,  load average: {_loadavg()}\r\n"
            "USER     TTY      LOGIN@   IDLE   WHAT\r\nubuntu   pts/0     11:02    0.00s  -bash\r\n")


W_SHORT = ""  # computed live via _w_short()

SYSTEMCTL_STATUS = (
    "● honey\r\n"
    "    State: running\r\n"
    "     Jobs: 0 queued\r\n"
    "   Failed: 0 units\r\n"
)

SERVICE_ALL = " [ + ]  apache2\r\n [ + ]  cron\r\n [ + ]  ssh\r\n"

JOURNAL_SHORT = "-- Logs begin at Tue 2026-09-03 07:55:12 UTC --\r\n"

PING_TMPL = (
    "PING {t} ({t}) 56(84) bytes of data.\r\n"
    "64 bytes from {t}: icmp_seq=1 ttl=53 time=12.4 ms\r\n"
    "64 bytes from {t}: icmp_seq=2 ttl=53 time=11.8 ms\r\n"
    "--- {t} ping statistics ---\r\n"
    "2 packets transmitted, 2 received, 0% packet loss, time 1001ms\r\n"
)

VERSIONS = {
    "python3": "Python 3.12.3\r\n",
    "python": "Python 3.12.3\r\n",
    "perl": "\r\nThis is perl 5, version 34, subversion 0 (v5.34.0) built for x86_64-linux-gnu-thread-multi\r\n",
    "ruby": "ruby 3.2.3 (2024-01-18 revision 52bb2ac0a6) [x86_64-linux-gnu]\r\n",
    "php": "PHP 8.3.6 (cli) (built: Apr 10 2026 12:40:38) (NTS)\r\n",
    "node": "v20.19.0\r\n",
    "gcc": "gcc (Ubuntu 13.2.0-23ubuntu4) 13.2.0\r\n",
    "git": "git version 2.43.0\r\n",
    "go": "go version go1.22.2 linux/amd64\r\n",
}

NOT_FOUND_TOOLS = {"nmap", "msfconsole", "msfvenom", "sqlmap", "hydra", "john", "hashcat", "gobuster", "nikto"}

# commands that exist at absolute paths too (/bin/uname, /usr/bin/nproc, ...)
KNOWN_CMDS = {
    "uname", "arch", "nproc", "lscpu", "lspci", "cat", "grep", "awk", "sed",
    "cut", "head", "tr", "dd", "sort", "uniq", "wc", "tac", "ls", "ps",
    "top", "free", "df", "du", "echo", "printf", "pwd", "whoami", "id",
    "hostname", "date", "who", "w", "last", "lastlog", "env", "printenv",
    "crontab", "systemctl", "service", "journalctl", "mount", "dmesg",
    "ifconfig", "ip", "ss", "netstat", "ping", "history", "python3",
    "python", "perl", "ruby", "php", "node", "gcc", "git", "docker",
    "mysql", "psql", "getconf", "command", "test", "[", "true", "false",
    "read", "which", "type", "lsb_release", "hostnamectl", "timedatectl",
    "nvidia-smi", "bash", "sh", "busybox", "toybox", "tee", "sleep",
    "clear", "alias", "kill", "chmod", "touch", "mkdir",
}


class ShellState:
    def __init__(self, username: str, src_ip: str):
        self.username = username
        self.src_ip = src_ip
        self.cwd = f"/home/{username}" if username else "/home/ubuntu"
        self.awaiting_sudo_pass = False
        self.pending_sudo_cmd = ""
        home = f"/home/{username}" if username else "/home/ubuntu"
        self.env = {"USER": username, "HOME": home, "PWD": self.cwd,
                    "SHELL": "/bin/bash", "LANG": "C.UTF-8",
                    "HOSTNAME": "honey",
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}


def prompt(st: ShellState) -> str:
    return f"\r\n{st.username}@honey:{st.cwd}$ "


def initial_greeting(st: ShellState) -> str:
    login = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    return MOTD + f"\r\nLast login: {login} from {st.src_ip}\r\n" + prompt(st)


def _expand(st: ShellState, text: str) -> str:
    import re as _re2
    home = f"/home/{st.username}"

    def _var(m):
        name = m.group(1) or m.group(2)
        if name in st.env:
            return st.env[name]
        return {"USER": st.username, "HOME": home, "PWD": st.cwd,
                "HOSTNAME": "honey"}.get(name, m.group(0))
    text = (text.replace("$USER", st.username).replace("${USER}", st.username)
            .replace("$HOME", home).replace("${HOME}", home)
            .replace("$PWD", st.cwd).replace("~", home)
            .replace("$HOSTNAME", "honey").replace("${HOSTNAME}", "honey"))
    return _re2.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)",
                    _var, text)


def handle_line(st: ShellState, line: str):
    """Entry point: compound lines go through the mini-shell."""
    raw = line.strip()
    if not raw:
        return prompt(st), None, None
    if st.awaiting_sudo_pass:
        st.awaiting_sudo_pass = False
        out = f"\r\nSorry, user {st.username} is not in the sudoers file. This incident will be reported.\r\n" + prompt(st)
        return out, f"[sudo-password] {raw}", "sudo-password"
    from . import minish as _ms
    if _ms.is_compound(raw):
        depth = getattr(st, "_depth", 0)
        if depth > 25:
            return "\r\nbash: recursion too deep\r\n" + prompt(st), raw, None
        st._depth = depth + 1
        try:
            body, code = _ms.run_script(st, raw)
        except _ms._Exit:
            body, code = "", 0
        finally:
            st._depth = depth
        st.env["PWD"] = st.cwd
        body = body.replace("\r\n", "\n")
        return "\r\n" + body.replace("\n", "\r\n") + "\r\n" + prompt(st), raw, None
    return handle_simple(st, raw)


def handle_simple(st: ShellState, line: str):
    """Single-command emulation (no shell operators). Never dispatches back."""
    raw = line.strip()
    if not raw:
        return prompt(st), None, None
    parts = raw.split()
    cmd = parts[0]
    # /bin/uname, /usr/bin/nproc, ./tool etc: resolve to basename when known
    if "/" in cmd:
        base = cmd.rsplit("/", 1)[-1]
        if base in KNOWN_CMDS:
            raw = base + raw[len(cmd):]
            parts = raw.split()
            cmd = parts[0]
    args = parts[1:]
    argstr = " ".join(args)

    def done(body: str, secret=None, kind=None):
        return "\r\n" + body + "\r\n" + prompt(st), secret if secret is not None else raw, kind

    if cmd == "sudo":
        if st.username == "root":
            # root needs no password: run the remainder in place.
            rest = raw[4:].strip()
            if not rest or rest.split()[0] == "sudo":
                return done("")
            out2, _, _ = handle_line(st, rest)
            return out2, raw, None
        if args and args[0] in ("-l", "-n", "-v", "--list"):
            return done(f"User {st.username} may run the following commands on honey:\r\n    (root) NOPASSWD: /usr/bin/systemctl status *", kind="privesc")
        st.awaiting_sudo_pass = True
        st.pending_sudo_cmd = raw
        return f"\r\n[sudo] password for {st.username}: ", raw, None
    if cmd in ("wget", "curl"):
        url = parts[-1] if len(args) > 0 else ""
        kind = "url" if url.startswith("http") else None
        if "|" in raw or args[:1] in (["-s"], ["-fsSL"], ["-qO-"]) or raw.rstrip().endswith("| bash") or "| sh" in raw or "| bash" in raw:
            kind = "url"
        return done("--%s--  Connecting... failed: Connection refused." % datetime.now().strftime("%Y-%m-%d %H:%M:%S"), kind=kind)
    if cmd in ("ssh", "scp", "sftp"):
        return done("ssh: connect to host port 22: Connection timed out", kind="lateral")
    if cmd == "echo":
        return done(_expand(st, argstr))
    if cmd == "export":
        return done("")
    if cmd == "whoami":
        return done(st.username)
    if cmd in ("id", "groups"):
        if st.username == "root":
            return done("uid=0(root) gid=0(root) groups=0(root)")
        return done(f"uid=1000({st.username}) gid=1000({st.username}) groups=1000({st.username})")
    if cmd == "pwd":
        return done(st.cwd)
    if cmd == "hostname":
        if args and args[0] == "-I":
            return done("10.0.2.15 172.17.0.2")
        return done("honey")
    if cmd == "uname":
        if "-a" in args or not args:
            return done(f"Linux honey 6.8.0-41-generic {UNAME_V} x86_64 x86_64 x86_64 GNU/Linux")
        out = []
        for a in args:
            if a == "-s":
                out.append("Linux")
            elif a == "-n":
                out.append("honey")
            elif a == "-r":
                out.append("6.8.0-41-generic")
            elif a == "-v":
                out.append(UNAME_V)
            elif a in ("-m", "-p", "-i"):
                out.append("x86_64")
            elif a == "-o":
                out.append("GNU/Linux")
        return done(" ".join(out) if out else "Linux")
    if cmd == "arch":
        return done("x86_64")
    if cmd == "nproc":
        return done(str(NCPU))
    if cmd == "lspci":
        return done(LSPCI.rstrip("\r\n"))
    if cmd == "nvidia-smi":
        if args and args[0] in ("-L", "--list-gpus"):
            return done("GPU 0: NVIDIA A100 PCIe 40GB (UUID: GPU-9d3b1f2c-4a5e-4b6f-8c7d-9e0f1a2b3c4d)")
        return done(_nvidia_smi().rstrip("\r\n"))
    if cmd == "uptime":
        if args and args[0] in ("-p", "--pretty"):
            d = int(_uptime_sec() // 86400)
            return done(f"up {d} days")
        if args and args[0] == "-s":
            return done("2026-09-03 07:55:12")
        return done(f" {datetime.now().strftime('%H:%M:%S')} up {_uptime_clock()},  1 user,  load average: {_loadavg()}")
    if cmd == "date":
        return done(datetime.now().strftime("%a %b %d %I:%M:%S %p UTC %Y"))
    if cmd == "who":
        return done("ubuntu   pts/0        2026-10-07 11:02 (203.0.113.44)")
    if cmd == "w":
        return done(_w_short().rstrip("\r\n"))
    if cmd == "last":
        return done(LAST_SHORT.rstrip("\r\n"))
    if cmd == "lastlog":
        return done("Username         Port     From             Latest")
    if cmd == "ls":
        if any(a.startswith("-") and ("l" in a) for a in args):
            return done(LS_LONG.rstrip("\r\n"))
        files = FAKE_FILES.get(st.cwd, ["app", "data", ".bashrc"])
        if not any(a.startswith("-") and ("a" in a) for a in args):
            files = [f for f in files if not f.startswith(".")]
        return done("  ".join(files))
    if cmd == "cd":
        if args:
            d = args[0]
            if d == "-":
                pass
            elif d.startswith("/"):
                st.cwd = d.rstrip("/") or "/"
            elif d == "..":
                st.cwd = "/" + "/".join([p for p in st.cwd.split("/") if p][:-1])
                if st.cwd == "/":
                    pass
                st.cwd = st.cwd or "/"
            else:
                st.cwd = (st.cwd.rstrip("/") + "/" + d).replace("//", "/")
        else:
            st.cwd = f"/home/{st.username}"
        return prompt(st), raw, None
    if cmd == "cat":
        target = args[-1] if args else ""
        if "shadow" in raw or "gshadow" in raw:
            if st.username == "root":
                return done(FAKE_SHADOW.rstrip("\r\n"))
            return done(f"cat: {target or '/etc/shadow'}: Permission denied")
        if "passwd" in raw:
            return done(FAKE_PASSWD.replace("\n", "\r\n").rstrip("\r\n"))
        if "os-release" in raw:
            return done(FAKE_OS_RELEASE.rstrip("\r\n"))
        if "hostname" in raw and "hosts" not in raw:
            return done("honey")
        if "hosts" in raw:
            return done(FAKE_HOSTS.rstrip("\r\n"))
        if "cpuinfo" in raw or "/proc/version" in raw:
            if "version" in raw and "cpuinfo" not in raw:
                return done("Linux version 6.8.0-41-generic (buildd@lcy02-amd64-101) #41-Ubuntu SMP PREEMPT_DYNAMIC")
            return done(FAKE_CPUINFO.rstrip("\r\n"))
        if "uptime" in raw and "/proc/" in raw:
            return done(_fake_uptime())
        if "meminfo" in raw:
            return done(FAKE_MEMINFO.rstrip("\r\n"))
        if "config.php" in raw:
            return done(FAKE_CONFIG_PHP.rstrip("\r\n"), kind="loot")
        if ".bash_history" in raw or ".bashrc" in raw:
            if "history" in raw:
                return done("cd /var/www\r\nls -la\r\ncat config.php\r\nexit")
            return done(FAKE_BASHRC.rstrip("\r\n"))
        if "authorized_keys" in raw or ".ssh" in raw:
            return done(f"cat: {target}: No such file or directory")
        return done(f"cat: {target or ''}: No such file or directory")
    if cmd == "ps":
        return done(PS_AUX.rstrip("\r\n"))
    if cmd == "top":
        return done(_top_snap().rstrip("\r\n"))
    if cmd == "htop":
        return done("Error opening terminal: unknown.")
    if cmd in ("free", "vmstat"):
        if "-g" in args:
            return done(FREE_G.rstrip("\r\n"))
        return done(FREE_M.rstrip("\r\n"))
    if cmd == "df":
        return done(DF_H.rstrip("\r\n"))
    if cmd == "du":
        return done("4.0K\t.\r\n28K\t./app".replace("\t", "  "))
    if cmd == "lscpu":
        return done(LSCPU_SHORT.rstrip("\r\n"))
    if cmd == "lsblk":
        return done(LSBLK.rstrip("\r\n"))
    if cmd in ("mount", "fdisk"):
        if cmd == "fdisk":
            return done("fdisk: cannot open /dev/sda: Permission denied")
        return done("/dev/sda1 on / type ext4 (rw,relatime)")
    if cmd == "dmesg":
        return done("dmesg: read kernel buffer failed: Operation not permitted")
    if cmd in ("ifconfig", "ip"):
        if args and args[0] in ("a", "addr", "address", "route", "r"):
            return done("1: lo: <LOOPBACK,UP> mtu 65536\r\n2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500\r\n    inet 10.0.2.15/24 scope global eth0")
        return done("eth0: inet 10.0.2.15  netmask 255.255.255.0  broadcast 10.0.2.255")
    if cmd in ("ss", "netstat"):
        return done(SS_LISTEN.rstrip("\r\n"))
    if cmd == "ping":
        target = args[-1] if args else "8.8.8.8"
        target = target.lstrip("-") if target.startswith("-") else target
        return done(PING_TMPL.format(t=target).rstrip("\r\n"))
    if cmd == "history":
        return done("    1  cd /var/www\r\n    2  ls -la\r\n    3  cat config.php")
    if cmd == "env":
        return done(f"USER={st.username}\r\nHOME=/home/{st.username}\r\nSHELL=/bin/bash\r\nPWD={st.cwd}\r\nLANG=C.UTF-8")
    if cmd == "crontab":
        return done(f"no crontab for {st.username}")
    if cmd == "systemctl":
        sub = args[0] if args else "status"
        if sub == "status" or not args:
            tgt = args[1] if len(args) > 1 else ""
            if tgt in ("ssh", "sshd"):
                return done("● ssh.service - OpenBSD Secure Shell server\r\n     Loaded: loaded (/lib/systemd/system/ssh.service; enabled)\r\n     Active: active (running)")
            return done(SYSTEMCTL_STATUS.rstrip("\r\n"))
        if sub in ("is-active", "is-enabled"):
            return done("active" if sub == "is-active" else "enabled")
        if sub in ("list-units", "list-unit-files"):
            return done("  ssh.service        loaded active running   OpenBSD Secure Shell server\r\n  cron.service       loaded active running   Regular background program processing daemon\r\n  apache2.service    loaded active running   The Apache HTTP Server")
        if sub in ("start", "stop", "restart", "reload", "enable", "disable"):
            return done(f"==== AUTHENTICATING FOR org.freedesktop.systemd1.manage-units ====\r\nAuthentication is required to {sub} '{args[1] if len(args) > 1 else ''}'.", kind="privesc")
        return done("")
    if cmd == "service":
        if len(args) >= 2 and args[1] in ("start", "stop", "restart", "status"):
            return done(f" * {args[0]} {args[1]} [ OK ]")
        return done(SERVICE_ALL.rstrip("\r\n"))
    if cmd == "journalctl":
        return done(JOURNAL_SHORT.rstrip("\r\n"))
    if cmd in ("touch", "mkdir", "rm", "cp", "mv", "chmod", "chown", "ln"):
        return done("")
    if cmd in ("find", "grep", "awk", "sed", "head", "tail", "less", "more", "cut", "sort", "uniq", "wc"):
        if cmd == "find":
            return done("./app\n./app/config.php\n./Documents")
        return done("")
    if cmd in ("nano", "vim", "vi"):
        return done(f"{cmd}: no write permission, starting in view-only mode -- use :q to quit")
    if cmd in VERSIONS:
        if not args or args[0] in ("--version", "-v", "-V"):
            return done(VERSIONS[cmd].rstrip("\r\n"))
        return done("")
    if cmd in ("pip", "pip3", "npm", "apt", "apt-get", "dpkg", "snap"):
        if cmd in ("apt", "apt-get"):
            return done("E: Could not open lock file /var/lib/dpkg/lock-frontend - open (13: Permission denied)")
        return done("")
    if cmd in ("git", "docker", "kubectl", "podman"):
        if cmd == "git":
            return done("usage: git [--version] [--help] <command> [<args>]")
        if cmd == "docker":
            return done("Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?")
        return done(f"{cmd}: command not found")
    if cmd in ("mysql", "psql", "redis-cli", "mongo", "mongosh", "sqlite3"):
        return done(f"{cmd}: could not connect: Connection refused", kind="loot")
    if cmd in ("passwd", "su", "adduser", "useradd", "usermod", "chpasswd"):
        return done(f"{cmd}: Permission denied.", kind="privesc")
    if cmd == "ssh-keygen":
        return done("Generating public/private ed25519 key pair.\r\nYour public key has been saved in /home/%s/.ssh/id_ed25519.pub" % st.username, kind="privesc")
    # --- realism pack: common recon / persistence / miner-dropper commands ---
    if cmd == "lsb_release":
        return done('Distributor ID:\tUbuntu\r\nDescription:\tUbuntu 24.04.1 LTS\r\nRelease:\t24.04\r\nCodename:\tnoble')
    if cmd == "hostnamectl":
        return done(" Static hostname: honey\r\n       Icon name: computer-vm\r\n         Machine ID: 9d3b1f2c4a5e4b6f8c7d9e0f1a2b3c4d\r\n            Boot ID: 1a2b3c4d5e6f7890abcdef1234567890\r\n  Virtualization: kvm\r\nOperating System: Ubuntu 24.04.1 LTS\r\n            Kernel: Linux 6.8.0-41-generic")
    if cmd == "timedatectl":
        return done("               Local time: " + datetime.now().strftime("%a %Y-%m-%d %H:%M:%S UTC") + "\r\n           Universal time: " + datetime.now().strftime("%a %Y-%m-%d %H:%M:%S UTC") + "\r\n                 Time zone: Etc/UTC (UTC, +0000)")
    if raw.startswith("cat /proc/"):
        if "version" in raw:
            return done("Linux version 6.8.0-41-generic (buildd@lcy02-amd64-101) #41-Ubuntu SMP PREEMPT_DYNAMIC")
        return done(f"cat: {args[-1] if args else ''}: No such file or directory")
    if cmd == "docker" or raw.startswith("docker "):
        if "ps" in raw:
            return done("CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES")
        return done("Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?")
    if cmd == "tac" and args and args[0].startswith("/proc/"):
        return done("Linux version 6.8.0-41-generic #41-Ubuntu SMP PREEMPT_DYNAMIC")
    if cmd in ("nc", "ncat", "netcat", "busybox"):
        return done(f"bash: {cmd}: command not found" if cmd == "busybox" else "Ncat: Connection timed out.", kind="lateral")
    if cmd in ("pkill", "kill", "killall", "nohup"):
        return done("")
    if cmd == "clear" or cmd == "reset":
        return done("\x1b[H\x1b[2J")
    if cmd == "alias":
        return done("alias ll='ls -alF'\r\nalias la='ls -A'")
    if cmd == "printenv" or (cmd == "env" and args and args[0] == "|"):
        return done(f"USER={st.username}\r\nHOME=/home/{st.username}\r\nSHELL=/bin/bash\r\nPWD={st.cwd}\r\nLANG=C.UTF-8")
    if raw.startswith("env | grep") or raw.startswith("printenv "):
        return done("")
    if cmd == "sleep":
        return done("")
    if cmd in ("python3", "python") and ("-c" in args or len(args) > 0 and args[0].endswith(".py")):
        return done("")
    if "xmrig" in raw or "miner" in raw or "kdevtmpfsi" in raw or "kinsing" in raw:
        return done("bash: ./xmrig: cannot execute binary file: Exec format error", kind="malware")
    if cmd == "chmod" and ("+x" in raw):
        return done("")
    if raw.endswith("&") or "nohup " in raw or "setsid " in raw:
        return done("[1] 1843")
    if cmd in ("tput", "stty", "screen", "tmux"):
        return done("")
    if cmd in ("useradd", "adduser") or raw.startswith("echo ") and ">>" in raw and ("passwd" in raw or "shadow" in raw or "authorized_keys" in raw):
        return done("bash: /etc/passwd: Permission denied", kind="privesc")
    if cmd in NOT_FOUND_TOOLS:
        return done(f"bash: {cmd}: command not found")
    if cmd.startswith("./") or cmd.startswith("/"):
        base = cmd.rsplit("/", 1)[-1]
        # executing a known directory or missing path: match real bash
        if cmd.rstrip("/") in FAKE_FILES or base in ("app", "snap", "html"):
            return done(f"bash: {cmd}: Is a directory")
        return done(f"bash: {cmd}: No such file or directory")
    return done(f"bash: {cmd}: command not found")
