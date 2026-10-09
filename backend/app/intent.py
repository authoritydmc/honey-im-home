"""Attacker intent classification for honeypot commands.

Rule-based, ordered by specificity. Used by /api/insights and shown in the
UI so operators see *what the attacker tried to do*, not just raw commands.
"""
import re

INTENTS = {
    "fingerprint": {
        "label": "System fingerprinting",
        "note": "Profiling hardware and OS (CPU/RAM/GPU, distro, uptime) to "
                "decide if this box is worth mining on or ransoming. Our fake "
                "32-core / 96GB / A100 profile is designed to look juicy.",
    },
    "shell_probe": {
        "label": "Shell detection",
        "note": "Checking which shell and tools exist (bash vs sh, busybox, "
                "toybox) and how errors look, to tailor the next payload and "
                "to detect sandboxes by their error messages.",
    },
    "miner": {
        "label": "Crypto mining attempt",
        "note": "Dropping or probing for a cryptocurrency miner (xmrig, "
                "kinsing, kdevtmpfsi). The A100 GPU bait makes this box look "
                "like a prime mining target.",
    },
    "lateral": {
        "label": "Lateral movement / exfiltration",
        "note": "Trying to reach other hosts or pull payloads (ssh/scp, "
                "netcat, curl/wget pipes, /dev/tcp). Blocked with fake "
                "timeouts and refused connections.",
    },
    "persistence": {
        "label": "Persistence attempt",
        "note": "Trying to survive reboots (cron, systemd units, SSH keys, "
                "profile/rc files). All writes are fake and vanish.",
    },
    "privesc": {
        "label": "Privilege escalation",
        "note": "Trying to become root (sudo, su, password changes, setuid, "
                "kernel exploits). The sudo password prompt harvests one "
                "more credential before refusing.",
    },
    "loot": {
        "label": "Credential / data theft",
        "note": "Hunting secrets: password files, configs, keys, shell "
                "history, databases. Served convincing-looking fakes (the "
                "config.php database password is bait).",
    },
    "destructive": {
        "label": "Destructive action",
        "note": "Trying to destroy evidence or the system (rm -rf /, disk "
                "wipes, reboot/poweroff, fork bombs). Nothing real executes.",
    },
    "recon_other": {
        "label": "General reconnaissance",
        "note": "Looking around the system (processes, users, network, "
                "files). All output is emulated.",
    },
}

_RULES = [
    ("miner", r"xmrig|miner\b|kinsing|kdevtmpfsi|stratum|nicehash|monero|pool\.\w+"),
    ("destructive", r"rm\s+-rf\s+/$|mkfs|dd\s+.*of=/dev|shutdown|reboot|halt|poweroff|:\(\)\s*\{\s*:\|"),
    ("fingerprint", r"uname|lscpu|nproc|getconf|lspci|nvidia-smi|/proc/(cpuinfo|version|uptime|meminfo|device-tree)|Cpus_allowed|device-tree|last\b|\bw\b|free\b|df\b|uptime|arch\b|device_model|cpu_model|gpu_info|filter_output|SHELL_BEHAVIOR"),
    ("shell_probe", r"command\s+-v|xxxxxx|which\s+\w+|type\s+\w+|echo\s+\$0|bash\s+-se|toybox|busybox"),
    ("lateral", r"\bssh\b|\bscp\b|\bsftp\b|\bnc\b|ncat|netcat|/dev/tcp|curl|wget|\|\s*(ba)?sh\b"),
    ("persistence", r"crontab|systemctl\s+(en|dis)able|/etc/cron|authorized_keys|rc\.local|\.bashrc|\.profile|/etc/systemd"),
    ("privesc", r"sudo|^\s*passwd\b|;\s*passwd\b|&&\s*passwd\b|\|\s*passwd\b|\bsu\b|adduser|useradd|chmod\s+\+s|setuid|/etc/shadow|exploit|cve-|dirty\s*cow|pkexec"),
    ("loot", r"/etc/passwd|config\.php|\.env|id_rsa|\.ssh|history|\benv\b|mysql|psql|redis-cli|mongosh|DB_PASS|shadow|gshadow"),
]


def classify(cmd: str):
    """Return (intent_key, matched) for a command string."""
    c = cmd or ""
    for key, pat in _RULES:
        if re.search(pat, c, re.I):
            return key, True
    if c.strip().startswith(("ls", "ps", "cat", "whoami", "id", "pwd", "echo", "lsb_release")):
        return "recon_other", True
    if len(c.strip()) < 3:
        return "recon_other", False
    return "recon_other", True


def summarize(commands):
    """Aggregate a list of command strings into insight cards.

    Returns list of {intent, label, note, count, examples}.
    """
    from collections import Counter
    counts: Counter = Counter()
    examples: dict[str, list] = {}
    for c in commands:
        key, _ = classify(c)
        counts[key] += 1
        ex = examples.setdefault(key, [])
        short = (c[:160] + "…") if len(c) > 160 else c
        if short not in ex and len(ex) < 3:
            ex.append(short)
    cards = []
    for key, n in counts.most_common():
        meta = INTENTS.get(key, INTENTS["recon_other"])
        cards.append({"intent": key, "label": meta["label"], "note": meta["note"],
                      "count": n, "examples": examples.get(key, [])})
    return cards
