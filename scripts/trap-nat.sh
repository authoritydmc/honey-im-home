#!/bin/bash
# Honey trap NAT: attackers on :22 -> honeypot :2222, admins on :2244 -> real sshd :22.
# Host sshd + systemd socket are NEVER touched. Fail-open: if NAT absent, :22 is real sshd.
# Usage: ./trap-nat.sh [--rollback]
set -euo pipefail
BEFORE=/etc/ufw/before.rules
BEFORE6=/etc/ufw/before6.rules
MARK="# honey-im-home trap NAT"

apply() {
  for f in $BEFORE $BEFORE6; do
    [ -f "$f" ] || { echo "no $f"; continue; }
    if grep -qF "$MARK" "$f"; then echo "[*] NAT already present in $f"; continue; fi
    sudo cp "$f" "$f.bak-$(date +%Y%m%d%H%M%S)"
    # insert NAT table before the *filter line (first occurrence)
    sudo python3 - "$f" <<'PY'
import sys
f = sys.argv[1]
mark = "# honey-im-home trap NAT"
nat = f"""*nat
:PREROUTING ACCEPT [0:0]
-A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 2222 {mark}
-A PREROUTING -p tcp --dport 2244 -j REDIRECT --to-port 22 {mark}
COMMIT
"""
t = open(f).read()
assert "*filter" in t, "no *filter in " + f
t = t.replace("*filter", nat + "\n*filter", 1)
open(f, "w").write(t)
print("patched", f)
PY
  done
  sudo ufw allow 2222/tcp comment 'Honeypot trap (NAT from 22)' || true
  sudo ufw allow 2244/tcp comment 'Real SSH via NAT to 22' || true
  sudo ufw allow 22/tcp comment 'SSH (trap from net, real from localhost)' || true
  sudo ufw reload
  echo "[*] active NAT:"; sudo iptables -t nat -L PREROUTING -n --line-numbers | grep -E 'REDIRECT|dpt:22|dpt:2244' || true
  echo "[*] test from OUTSIDE this box (localhost :22 stays real sshd by design):"
  echo "    ssh -p 22 ubuntu@<public-ip>    # expect Ubuntu trap banner + accept-all"
  echo "    ssh -p 2244 ubuntu@<public-ip>  # expect REAL host (key-only)"
}

rollback() {
  for f in $BEFORE $BEFORE6; do
    [ -f "$f" ] || continue
    sudo sed -i "/honey-im-home trap NAT/d" "$f"
    # drop empty *nat block if left behind (harmless if kept, but tidy)
    sudo python3 - "$f" <<'PY'
import sys, re
f = sys.argv[1]
t = open(f).read()
t = re.sub(r"\*nat\n:PREROUTING ACCEPT \[0:0\]\nCOMMIT\n\n?", "", t)
open(f, "w").write(t)
PY
  done
  sudo ufw reload
  echo "[*] rolled back; :22 is real sshd again everywhere"
}

case "${1:-}" in
  --rollback) rollback ;;
  *) apply ;;
esac
