#!/bin/bash
# Deploy honey-im-home on an Oracle host (Coolify network + Traefik + UFW + OCI).
# Run from repo root on the server. Idempotent.
set -euo pipefail
REAL_PORT=2244
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "copy .env.example to .env first"; exit 1; }
# 1. UFW baseline (run before sshd finalize so you never lock out)
sudo ufw --force enable || true
sudo ufw allow $REAL_PORT/tcp comment 'Real SSH after honey swap' || true
sudo ufw allow 22/tcp comment 'Honeypot SSH trap' || true
sudo ufw allow 80/tcp comment 'HTTP Traefik' || true
sudo ufw allow 443/tcp comment 'HTTPS Traefik' || true
sudo ufw allow 443/udp comment 'HTTP3 QUIC' || true
sudo ufw allow 41641/udp comment 'Tailscale' || true
# API 8078 stays localhost-only in prod compose; no UFW open needed.
# If you need direct tailnet access (no Traefik), uncomment:
# sudo ufw allow in on tailscale0 to any port 8078 proto tcp comment 'Honey UI via tailnet' || true
sudo ufw status verbose
# 2. Coolify external network for Traefik discovery
docker network inspect coolify >/dev/null 2>&1 || docker network create coolify
# 3. Build + start (honeypot binds host :22, so run scripts/swap-ssh-port.sh --finalize FIRST)
docker compose -f docker-compose.prod.yml up -d --build
sleep 5
curl -fsS http://127.0.0.1:8078/healthz
# 4. Honeypot smoke: password is always accepted, key is logged+rejected
(sshpass -p trap123 ssh -p 22 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 ubuntu@127.0.0.1 "whoami; exit" 2>&1 | head -5) || true
echo "--- recent creds (needs JWT) ---"
echo "login: curl -s -X POST 127.0.0.1:8078/api/auth/login -H 'Content-Type: application/json' -d '{\"password\":\"\$ADMIN_PASSWORD\"}'"
docker ps --format '{{.Names}} {{.Ports}} {{.Status}}' | grep -i honey
