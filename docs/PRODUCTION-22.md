# Production: honeypot on real port 22, real SSH on 2244

Goal: attackers hitting `:22` get the trap. You SSH to `:2244`. Admin UI `https://honey.rajlabs.in` behind Authentik SSO via Traefik. API never public directly.

## Architecture after swap

```
internet :22 ──▶ honey-im-home docker (2222 internal) ──▶ sqlite + :8078 UI
internet :2244 ─▶ real sshd (host) — UFW restricted, key-only
internet :80/443 ─▶ coolify-proxy Traefik ──▶ honey:8078 (with authentik-auth middleware)
tailnet ─▶ real sshd :2244 + honey UI (backup)
```

## 0. Prerequisites

* `.env` with `ADMIN_PASSWORD`, `SECRET_KEY` (32+ chars). Same file on both servers or per-host secrets.
* DNS: `honey.rajlabs.in` A → `80.225.195.202` (server1). Start with server1 only; add server2 later or use `honey2.rajlabs.in`.
* OCI Security List currently allows `22,80,443,53,853`. You must ADD `2244/tcp 0.0.0.0/0` (or your IP + tailnet) before moving sshd, else lockout.
* Keep an active SSH session open the whole time. Test every step in a second terminal.

## 1. Open OCI for real SSH (do first)

```bash
# find your security-list id
oci network security-list list -c $TENANCY --all | grep -B2 -A2 'Default Security'
# add 2244 ingress (repeat for both VCNs: rajlabs-public-vcn + rajlabs-vcn-2)
oci network security-list update --security-list-id ocid1.securitylist.oc1... \
  --ingress-security-rules '[{"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":2244,"max":2244}}}]' --force
# verify
oci network security-list get --security-list-id ocid1... | grep -A2 2244
```

Or in OCI Console: Networking → VCN → Security Lists → Default → Add Ingress: TCP source `0.0.0.0/0` dest port `2244`. Repeat for IPv6 `::/0` if used.

## 2. UFW changes (both servers, before sshd move)

```bash
sudo ufw --force enable
sudo ufw allow 2244/tcp comment 'Real SSH after honey swap'
sudo ufw allow 22/tcp comment 'Honeypot SSH trap'
sudo ufw allow 80/tcp comment 'HTTP Traefik'
sudo ufw allow 443/tcp comment 'HTTPS Traefik'
sudo ufw allow 443/udp comment 'HTTP3 QUIC'
sudo ufw allow 41641/udp comment 'Tailscale'
# Do NOT open 8078 publicly. Prod compose binds it to 127.0.0.1 only.
# Optional tailnet-only direct UI:
# sudo ufw allow in on tailscale0 to any port 8078 proto tcp comment 'Honey UI via tailnet'
sudo ufw status verbose
```

Docker note: honeypot port `22:2222` is a published port so UFW `allow 22` is the visible rule; `DOCKER-USER` chain still enforces. API `127.0.0.1:8078:8078` never hits UFW INPUT from outside.

## 3. Move real sshd 22 → 2244 (safe two-phase)

Phase 1 — listen on both, keep 22 working:

```bash
./scripts/swap-ssh-port.sh
# in a SECOND terminal, must succeed before continuing:
ssh -p 2244 ubuntu@SERVER_IP
sudo sshd -T | grep -i '^port '
```

Phase 2 — after honey is ready to own host 22:

```bash
./scripts/swap-ssh-port.sh --finalize
ss -tlnp | grep -E ':22|:2244'   # :22 should be free (no sshd), :2244 sshd
```

Rollback any time: `./scripts/swap-ssh-port.sh --rollback`.

Update local client `~/.ssh/config`:

```
Host oracle1
  HostName 80.225.195.202
  User ubuntu
  Port 2244
  IdentityFile ~/.ssh/oracle.key

Host oracle2
  HostName 130.210.3.9
  User ubuntu
  Port 2244
  IdentityFile ~/.ssh/oracle.key

# trap targets (intentional: port 22 = honeypot)
Host oracle1-trap
  HostName 80.225.195.202
  User root
  Port 22
  IdentityFile ~/.ssh/oracle.key
```

## 4. Deploy honey + Traefik SSO

```bash
cp .env.example .env   # set ADMIN_PASSWORD + SECRET_KEY
docker network inspect coolify >/dev/null || docker network create coolify
./scripts/deploy-honey.sh
# copy file-provider fallback (optional if labels fail):
sudo cp examples/traefik-honey.yaml /data/coolify/proxy/dynamic/honey.yaml
```

Traefik: `honey.rajlabs.in` → `honey:8078` with `authentik-auth@file` middleware (same as `authentik.yaml`). HTTP→HTTPS via `redirect-to-https@file`. LetsEncrypt `letsencrypt` resolver. No bypass paths — every `/api/*` needs JWT or `X-Forwarded-User` when `TRUST_PROXY_AUTH=1`.

Verify:

```bash
curl -s http://127.0.0.1:8078/healthz  # {"ok": true}
ssh -p 22 -o StrictHostKeyChecking=no ubuntu@SERVER_IP "whoami; pwd; ls; exit"
# then with JWT:
TOKEN=$(curl -s -X POST 127.0.0.1:8078/api/auth/login -H 'Content-Type: application/json' -d '{"password":"..."}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
curl -s 127.0.0.1:8078/api/stats -H "Authorization: Bearer $TOKEN" | head -c 500
curl -sk https://honey.rajlabs.in/healthz  # via Traefik, should prompt Authentik login first in browser
```

## 5. Both servers

* Server1 (`80.225.195.202`, ARM 2C/12G): primary honey + public `honey.rajlabs.in`. Full dataset.
* Server2 (`130.210.3.9`, 1G Micro, load ~20): run honey ONLY if RAM allows; otherwise keep as real-SSH-only + Tailscale exit-node. If enabled, use `honey2.rajlabs.in` or ship logs to server1 later. Do not run two heavy stacks on 1G box.

Order: server1 → verify 24h → server2.

## 6. Operational notes

* Logs: `/srv/data` volume (`honey.db` + `events.jsonl` + `ssh_host_key`). Back up volume. Retention `RETENTION_DAYS=90` (roadmap).
* Fail2ban still guards real `:2244`; honey `:22` accepts everything by design — never point fail2ban at it.
* Abuse: honey never dials out; `wget/curl` URLs only logged then refused.
* Updates: `docker compose -f docker-compose.prod.yml pull && up -d`.
