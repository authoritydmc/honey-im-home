#!/bin/bash
# Honey trap NAT (final design): direct iptables rules, UFW files carry filter only.
# - public :22 -> DNAT to honey container stable IP (attacker source IP preserved;
#   REDIRECT would bounce via docker-proxy and mask source as gateway)
# - public :2244 -> REDIRECT to host :22 (real sshd, untouched + socket-activated)
# Host sshd + ssh.socket are NEVER modified. Fail-open: no rules => :22 is real sshd.
# Persistence: examples/systemd-honey-nat.service (do NOT put NAT in UFW before.rules:
# ufw reload re-applies file content without flush and duplicates rules).
# Usage: HONEY_IP=10.0.2.50 HONEY_PORT=2222 ./scripts/trap-nat.sh [--rollback]
set -euo pipefail
HIP="${HONEY_IP:-10.0.2.50}"
HPORT="${HONEY_PORT:-2222}"
HIP6="${HONEY_IP6:-fdc9:f46e:be08::50}"

apply() {
  for spec in "-p tcp --dport 22 -j DNAT --to-destination $HIP:$HPORT" "-p tcp --dport 2244 -j REDIRECT --to-port 22"; do
    sudo iptables -t nat -C PREROUTING $spec 2>/dev/null || sudo iptables -t nat -I PREROUTING 1 $spec
  done
  for spec in "-p tcp --dport 22 -j DNAT --to-destination [$HIP6]:$HPORT" "-p tcp --dport 2244 -j REDIRECT --to-port 22"; do
    sudo ip6tables -t nat -C PREROUTING $spec 2>/dev/null || sudo ip6tables -t nat -I PREROUTING 1 $spec
  done
  sudo ufw route allow proto tcp from any to "$HIP" port "$HPORT" comment 'Honeypot trap DNAT' 2>/dev/null || true
  sudo ufw route allow proto tcp from any to "$HIP6" port "$HPORT" comment 'Honeypot trap DNAT6' 2>/dev/null || true
  sudo ufw allow 2222/tcp comment 'Honeypot trap direct' || true
  sudo ufw allow 2244/tcp comment 'Real SSH via NAT to 22' || true
  sudo ufw allow 22/tcp comment 'SSH (trap from net, real from localhost)' || true
  echo "[*] live NAT:"; sudo iptables -t nat -L PREROUTING -n | grep -E 'DNAT|REDIRECT'
}

rollback() {
  sudo iptables -t nat -D PREROUTING -p tcp --dport 22 -j DNAT --to-destination "$HIP:$HPORT" 2>/dev/null || true
  sudo iptables -t nat -D PREROUTING -p tcp --dport 2244 -j REDIRECT --to-port 22 2>/dev/null || true
  sudo ip6tables -t nat -D PREROUTING -p tcp --dport 22 -j DNAT --to-destination "[$HIP6]:$HPORT" 2>/dev/null || true
  sudo ip6tables -t nat -D PREROUTING -p tcp --dport 2244 -j REDIRECT --to-port 22 2>/dev/null || true
  echo "[*] rolled back; :22 is real sshd again everywhere (no reload needed)"
}

case "${1:-}" in
  --rollback) rollback ;;
  *) apply ;;
esac
