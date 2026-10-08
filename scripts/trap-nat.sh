#!/bin/bash
# Honey trap NAT: attackers on :22 -> honeypot container (stable IP, source preserved),
# admins on :2244 -> real sshd :22.
# Host sshd + systemd socket are NEVER touched. Fail-open: if NAT absent, :22 is real sshd.
# NOTE: iptables-restore (UFW before.rules) forbids trailing '#' comments, so rules
# carry '-m comment --comment honey-trap|honey-realssh' markers instead.
# REDIRECT would send :22 to host-local :2222 (docker-proxy masks source IP as gateway),
# so :22 goes via DNAT straight to the honey container IP instead.
# Usage: ./trap-nat.sh [--rollback]
HONEY_IP="${HONEY_IP:-10.0.2.50}"
HONEY_PORT="${HONEY_PORT:-2222}"
set -euo pipefail
BEFORE=/etc/ufw/before.rules
BEFORE6=/etc/ufw/before6.rules

apply() {
  for f in $BEFORE $BEFORE6; do
    [ -f "$f" ] || { echo "no $f"; continue; }
    if grep -qE 'honey-trap|honey-realssh' "$f"; then echo "[*] NAT already present in $f"; continue; fi
    sudo cp "$f" "$f.bak-$(date +%Y%m%d%H%M%S)"
    sudo python3 - "$f" <<'PY'
import os, sys
f = sys.argv[1]
hip = os.environ.get("HONEY_IP", "10.0.2.50")
hport = os.environ.get("HONEY_PORT", "2222")
t = open(f).read()
nat = ('*nat\n:PREROUTING ACCEPT [0:0]\n'
       '-A PREROUTING -p tcp --dport 22 -m comment --comment "honey-trap" -j DNAT --to-destination %s:%s\n' % (hip, hport) +
       '-A PREROUTING -p tcp --dport 2244 -m comment --comment "honey-realssh" -j REDIRECT --to-port 22\n'
       'COMMIT\n\n')
assert '*filter' in t, 'no *filter in ' + f
t = t.replace('*filter', nat + '*filter', 1)
open(f, 'w').write(t)
print('patched', f)
PY
  done
  sudo ufw route allow proto tcp from any to "$HONEY_IP" port "$HONEY_PORT" comment 'Honeypot trap DNAT' || true
  sudo ufw allow 2222/tcp comment 'Honeypot trap direct' || true
  sudo ufw allow 2244/tcp comment 'Real SSH via NAT to 22' || true
  sudo ufw allow 22/tcp comment 'SSH (trap from net, real from localhost)' || true
  sudo ufw reload
  echo "[*] active NAT:"; sudo iptables -t nat -L PREROUTING -n --line-numbers | grep -E 'REDIRECT|DNAT' || true
  echo "[*] test from OUTSIDE this box (localhost :22 stays real sshd by design):"
  echo "    ssh -p 22 ubuntu@<public-ip>    # trap"
  echo "    ssh -p 2244 ubuntu@<public-ip>  # real host (key-only)"
}

rollback() {
  for f in $BEFORE $BEFORE6; do
    [ -f "$f" ] || continue
    sudo sed -i '/honey-trap/d; /honey-realssh/d' "$f"
    sudo python3 - "$f" <<'PY'
import sys, re
f = sys.argv[1]
t = open(f).read()
t = re.sub(r'\*nat\n:PREROUTING ACCEPT \[0:0\]\nCOMMIT\n\n?', '', t)
open(f, 'w').write(t)
PY
  done
  sudo ufw route delete allow proto tcp from any to "${HONEY_IP:-10.0.2.50}" port "${HONEY_PORT:-2222}" 2>/dev/null || true
  sudo ufw reload
  echo "[*] rolled back; :22 is real sshd again everywhere"
}

case "${1:-}" in
  --rollback) rollback ;;
  *) apply ;;
esac
