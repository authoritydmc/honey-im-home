#!/bin/bash
# Safe SSH port swap: keep 22 AND add 2244, verify, then honey takes 22.
# Usage: ./swap-ssh-port.sh [--finalize | --rollback]
#  no args    : phase 1 - listen on 22 + 2244, open UFW, reload, test
#  --finalize : phase 2 - after honey owns 22, drop 22 so sshd only on 2244
#  --rollback : restore sshd to 22 only
set -euo pipefail
REAL_PORT=2244
SSHD_D=/etc/ssh/sshd_config.d/60-real-port.conf

phase1() {
  echo "[*] Phase 1: sshd on 22 + $REAL_PORT"
  echo "Port 22" | sudo tee $SSHD_D >/dev/null
  echo "Port $REAL_PORT" | sudo tee -a $SSHD_D >/dev/null
  sudo sshd -t
  sudo systemctl reload sshd
  echo "[*] UFW: allow $REAL_PORT, keep 22 for now (honey will take it)"
  sudo ufw allow $REAL_PORT/tcp comment 'Real SSH after honey swap' || true
  # NOTE: do NOT delete 22 yet - honey container needs host 22 free only in phase 2
  sudo ufw status numbered | head -n 40
  echo "[*] Test in ANOTHER terminal before continuing:"
  echo "    ssh -p $REAL_PORT ubuntu@\$(hostname -I | awk '{print \$1}')"
  echo "    sudo sshd -T | grep -i '^port '   # expect 22 and $REAL_PORT"
}

finalize() {
  echo "[*] Phase 2: sshd ONLY on $REAL_PORT (host 22 must be free for honey)"
  echo "Port $REAL_PORT" | sudo tee $SSHD_D >/dev/null
  sudo sshd -t
  sudo systemctl reload sshd
  echo "[*] UFW: honey owns 22 publicly, real SSH restricted"
  sudo ufw allow 22/tcp comment 'Honeypot SSH trap' || true
  sudo ufw allow $REAL_PORT/tcp comment 'Real SSH after honey swap' || true
  # Optional hardening: restrict real port to tailnet + your home IP:
  #   sudo ufw delete allow $REAL_PORT/tcp
  #   sudo ufw allow in on tailscale0 to any port $REAL_PORT proto tcp
  sudo sshd -T | grep -i '^port '
  sudo ss -tlnp | grep -E ':22|:2244'
  echo "[!] Now start honey: docker compose -f docker-compose.prod.yml up -d"
}

rollback() {
  echo "[*] Rollback: sshd back to 22 only"
  sudo rm -f $SSHD_D
  sudo systemctl reload sshd
  sudo sshd -T | grep -i '^port '
}

case "${1:-}" in
  --finalize) finalize ;;
  --rollback) rollback ;;
  *) phase1 ;;
esac
