#!/bin/bash
# Deploy honey-im-home on an Oracle host (Coolify network + Traefik + UFW NAT + OCI).
# Host sshd is NEVER moved. Run from repo root on the server. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "copy .env.example to .env first (ADMIN_PASSWORD, SECRET_KEY)"; exit 1; }
# 1. UFW baseline (NAT REDIRECT does the steering; sshd untouched)
sudo ufw --force enable || true
sudo ufw allow 2244/tcp comment 'Real SSH via NAT to 22' || true
sudo ufw allow 22/tcp comment 'SSH (trap from net, real from localhost)' || true
sudo ufw allow 2222/tcp comment 'Honeypot trap (NAT from 22)' || true
sudo ufw allow 80/tcp comment 'HTTP Traefik' || true
sudo ufw allow 443/tcp comment 'HTTPS Traefik' || true
sudo ufw allow 443/udp comment 'HTTP3 QUIC' || true
sudo ufw allow 41641/udp comment 'Tailscale' || true
# API 8078 stays localhost-only in prod compose; no UFW open needed.
# Optional tailnet-only direct UI:
# sudo ufw allow in on tailscale0 to any port 8078 proto tcp comment 'Honey UI via tailnet' || true
# 2. NAT steering :22 -> :2222 (trap), :2244 -> :22 (real). Fail-open, rollback with --rollback.
./scripts/trap-nat.sh
# 3. Coolify external network for Traefik discovery
docker network inspect coolify >/dev/null 2>&1 || docker network create coolify
# 4. Build + start
docker compose -f docker-compose.prod.yml up -d --build
sleep 8
curl -fsS http://127.0.0.1:8078/healthz
echo
echo "--- trap self-test (localhost :2222 hits honey directly; localhost :22 stays real by design) ---"
python3 - <<'PY'
import asyncio, asyncssh
async def t():
    async with asyncssh.connect('127.0.0.1', port=2222, username='root', password='smoke-test', known_hosts=None) as c:
        r = await c.run('whoami')
        print("trap whoami ->", repr(r.stdout[:80]))
asyncio.run(t())
PY
echo "--- from OUTSIDE this box verify: ssh -p 22 (trap) vs ssh -p 2244 (real) ---"
docker ps --format '{{.Names}} {{.Ports}} {{.Status}}' | grep -i honey
