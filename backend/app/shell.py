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

FAKE_OS_RELEASE = (
    'NAME="Ubuntu"\r\nVERSION="24.04.1 LTS (Noble Numbat)"\r\nID=ubuntu\r\n'
    'PRETTY_NAME="Ubuntu 24.04.1 LTS"\r\nVERSION_ID="24.04"\r\n'
)

FAKE_HOSTS = "127.0.0.1 localhost\r\n127.0.1.1 prod-server\r\n"

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

FAKE_CPUINFO = (
    "processor\t: 0\r\nvendor_id\t: GenuineIntel\r\n"
    "model name\t: Intel(R) Xeon(R) Platinum 8488C\r\n"
    "cpu MHz\t\t: 2992.969\r\nprocessor\t: 1\r\n"
    "model name\t: Intel(R) Xeon(R) Platinum 8488C\r\n"
)

FAKE_MEMINFO = (
    "MemTotal:        4024548 kB\r\nMemFree:         2876116 kB\r\n"
    "MemAvailable:    3420900 kB\r\nSwapTotal:             0 kB\r\n"
)

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

TOP_SNAP = (
    "top - 11:02:14 up 34 days,  2:11,  1 user,  load average: 0.08, 0.03, 0.01\r\n"
    "Tasks: 112 total,   1 running, 111 sleeping,   0 stopped,   0 zombie\r\n"
    "%Cpu(s):  2.1 us,  0.7 sy,  0.0 ni, 97.0 id,  0.1 wa,  0.0 hi,  0.1 si\r\n"
    "MiB Mem :   3930.2 total,   2808.4 free,    612.8 used,    509.0 buff/cache\r\n"
    "    PID USER      PR  NI    VIRT    RES  %CPU  %MEM     TIME+ COMMAND\r\n"
    "    812 www-data  20   0   41200  18200   1.2   0.4   0:11.32 apache2\r\n"
)

SS_LISTEN = (
    "State  Recv-Q Send-Q  Local Address:Port   Peer Address:Port\r\n"
    "LISTEN 0      4096        127.0.0.1:3306        0.0.0.0:*\r\n"
    "LISTEN 0      128           0.0.0.0:80          0.0.0.0:*\r\n"
    "LISTEN 0      128           0.0.0.0:22          0.0.0.0:*\r\n"
    "LISTEN 0      128              [::]:80             [::]:*\r\n"
)

DF_H = (
    "Filesystem      Size  Used Avail Use% Mounted on\r\n"
    "/dev/sda1        49G   14G   33G  30% /\r\n"
    "tmpfs           2.0G     0  2.0G   0% /dev/shm\r\n"
)

FREE_M = (
    "               total        used        free      shared  buff/cache   available\r\n"
    "Mem:            3930         612        2808          12         509        3340\r\n"
    "Swap:              0           0           0\r\n"
)

LSCPU_SHORT = (
    "Architecture:             x86_64\r\n"
    "  CPU(s):                 2\r\n"
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

W_SHORT = " 11:02:14 up 34 days,  2:11,  1 user,  load average: 0.08, 0.03, 0.01\r\nUSER     TTY      LOGIN@   IDLE   WHAT\r\nubuntu   pts/0     11:02    0.00s  -bash\r\n"

SYSTEMCTL_STATUS = (
    "● prod-server\r\n"
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


def _expand(st: ShellState, text: str) -> str:
    home = f"/home/{st.username}"
    return (text.replace("$USER", st.username).replace("${USER}", st.username)
            .replace("$HOME", home).replace("${HOME}", home)
            .replace("$PWD", st.cwd).replace("~", home))


def handle_line(st: ShellState, line: str):
    """Returns (output_to_send, command_to_log_or_None, secret_kind)."""
    raw = line.strip()
    if not raw:
        return prompt(st), None, None
    # sudo password capture
    if st.awaiting_sudo_pass:
        st.awaiting_sudo_pass = False
        out = f"\r\nSorry, user {st.username} is not in the sudoers file. This incident will be reported.\r\n" + prompt(st)
        return out, f"[sudo-password] {raw}", "sudo-password"
    parts = raw.split()
    cmd = parts[0]
    args = parts[1:]
    argstr = " ".join(args)

    def done(body: str, secret=None, kind=None):
        return "\r\n" + body + "\r\n" + prompt(st), secret if secret is not None else raw, kind

    if cmd == "sudo":
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
        return done(f"uid=1000({st.username}) gid=1000({st.username}) groups=1000({st.username})")
    if cmd == "pwd":
        return done(st.cwd)
    if cmd == "hostname":
        if args and args[0] == "-I":
            return done("10.0.2.15 172.17.0.2")
        return done("prod-server")
    if cmd == "uname":
        if "-a" in args or not args:
            return done("Linux prod-server 6.8.0-41-generic #41-Ubuntu SMP x86_64 GNU/Linux")
        if "-r" in args:
            return done("6.8.0-41-generic")
        if "-m" in args or "-p" in args:
            return done("x86_64")
        return done("Linux")
    if cmd == "arch":
        return done("x86_64")
    if cmd == "uptime":
        return done(" 11:02:14 up 34 days,  2:11,  1 user,  load average: 0.08, 0.03, 0.01")
    if cmd == "date":
        return done(datetime.now().strftime("%a %b %d %I:%M:%S %p UTC %Y"))
    if cmd == "who":
        return done("ubuntu   pts/0        2026-10-07 11:02 (203.0.113.44)")
    if cmd == "w":
        return done(W_SHORT.rstrip("\r\n"))
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
            return done(f"cat: {target or '/etc/shadow'}: Permission denied")
        if "passwd" in raw:
            return done(FAKE_PASSWD.replace("\n", "\r\n").rstrip("\r\n"))
        if "os-release" in raw:
            return done(FAKE_OS_RELEASE.rstrip("\r\n"))
        if "hostname" in raw and "hosts" not in raw:
            return done("prod-server")
        if "hosts" in raw:
            return done(FAKE_HOSTS.rstrip("\r\n"))
        if "cpuinfo" in raw:
            return done(FAKE_CPUINFO.rstrip("\r\n"))
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
        return done(TOP_SNAP.rstrip("\r\n"))
    if cmd == "htop":
        return done("Error opening terminal: unknown.")
    if cmd in ("free", "vmstat"):
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
        return done("no crontab for ubuntu")
    if cmd == "systemctl":
        sub = args[0] if args else "status"
        if sub == "status" or not args:
            return done(SYSTEMCTL_STATUS.rstrip("\r\n"))
        return done("")
    if cmd == "service":
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
    if cmd in NOT_FOUND_TOOLS:
        return done(f"bash: {cmd}: command not found")
    if cmd.startswith("./") or cmd.startswith("/"):
        return done(f"bash: {cmd}: Permission denied")
    return done(f"bash: {cmd}: command not found")
