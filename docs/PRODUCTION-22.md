# Production: honeypot owns public :22, real SSH on :2244 — without touching sshd

Design change (2026-10-08): host `sshd` / `ssh.socket` are NEVER modified.
Steering is done in UFW NAT (`/etc/ufw/before.rules`), which is fail-open:
if NAT is absent, `:22` is the real sshd exactly as before. Rollback is 3 lines.

## Traffic map after `./scripts/trap-nat.sh`

```
internet :22   ──PREROUTING REDIRECT──▶ host :2222 ──▶ honey docker (asyncssh trap)
internet :2244 ──PREROUTING REDIRECT──▶ host :22   ──▶ real sshd (key-only, fail2ban)
tailnet  :22   ──same PREROUTING──────▶ trap            (use :2244 on tailnet for real)
localhost :22  ──OUTPUT chain, no NAT─▶ real sshd       (by design; test trap via :2222 locally)
internet :80/443 ─▶ coolify-proxy Traefik ─▶ honey:8078 (authentik-auth SSO)
```

Attacker source IPs are preserved through REDIRECT (DNAT, not proxy), so
fail2ban-style intel, geo, and per-IP timelines in the UI stay accurate.
The honeypot container is fully isolated: no host network, `cap_drop: ALL`,
`no-new-privileges`, only `/srv/data` volume + published `2222`/`127.0.0.1:8078`.
It can never reach the internal network: it makes zero egress connections
(fake `wget/curl` only log the URL then refuse; no sockets dial out).

## 0. Prerequisites

* `.env` with `ADMIN_PASSWORD`, `SECRET_KEY` (32+ chars).
* DNS: `honey.rajlabs.in` A → server1 (`80.225.195.202`). Server2 later or `honey2.`.
* OCI ingress already includes `2244/tcp` (added 2026-10-08 to both default SLs).
* Keep one SSH session open. Every step below is rollback-safe.

## 1. UFW (both servers)

`./scripts/deploy-honey.sh` does this, equivalent manual:

```bash
sudo ufw --force enable
sudo ufw allow 2244/tcp comment 'Real SSH via NAT to 22'
sudo ufw allow 22/tcp comment 'SSH (trap from net, real from localhost)'
sudo ufw allow 2222/tcp comment 'Honeypot trap (NAT from 22)'
sudo ufw allow 80/tcp comment 'HTTP Traefik'
sudo ufw allow 443/tcp comment 'HTTPS Traefik'
sudo ufw allow 443/udp comment 'HTTP3 QUIC'
sudo ufw allow 41641/udp comment 'Tailscale'
# 8078 stays 127.0.0.1-only. No public rule.
```

Why allow `2222` in UFW: DNAT happens before filter, so redirected packets
are filtered on final dport `2222`. Denying it would blackhole the trap.

## 2. NAT steering (both servers)

```bash
./scripts/trap-nat.sh            # apply
./scripts/trap-nat.sh --rollback # revert: :22 real everywhere again
```

This inserts into `/etc/ufw/before.rules` (+`before6.rules`):

```
*nat
:PREROUTING ACCEPT [0:0]
-A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 2222
-A PREROUTING -p tcp --dport 2244 -j REDIRECT --to-port 22
COMMIT
```

then `ufw reload`. Verify: `sudo iptables -t nat -L PREROUTING -n`.

## 3. Deploy honey + Traefik SSO

```bash
cp .env.example .env   # set ADMIN_PASSWORD + SECRET_KEY
docker network inspect coolify >/dev/null || docker network create coolify
./scripts/deploy-honey.sh
sudo cp examples/traefik-honey.yaml /data/coolify/proxy/dynamic/honey.yaml  # fallback if labels fail
```

Traefik: `honey.rajlabs.in` → `honey:8078` with `authentik-auth@file`
(same middleware as `authentik.yaml`), HTTP→HTTPS via `redirect-to-https@file`,
LetsEncrypt resolver. Every `/api/*` needs JWT or `X-Forwarded-User` (`TRUST_PROXY_AUTH=1`).

Verify from OUTSIDE (from your laptop/WSL — localhost :22 bypasses NAT by design):

```bash
ssh -p 22 -o StrictHostKeyChecking=no ubuntu@SERVER_IP "whoami; pwd; ls; exit"   # trap answers
ssh -p 2244 -i ~/.ssh/oracle.key ubuntu@SERVER_IP "whoami"                        # real host
TOKEN=$(curl -s -X POST http://127.0.0.1:8078/api/auth/login -H 'Content-Type: application/json' -d '{"password":"..."}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
curl -s 127.0.0.1:8078/api/stats -H "Authorization: Bearer $TOKEN" | head -c 300
# browser: https://honey.rajlabs.in  (Authentik login first)
```

## 4. Client config (`~/.ssh/config`)

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
```

Port 22 on both hosts is now the trap — do NOT point admin SSH at it.

## 5. Both servers

* Server1 (`80.225.195.202`): primary honey + public `honey.rajlabs.in`.
* Server2 (`130.210.3.9`, 1G RAM): same NAT + honey with 512m cap; if docker
  struggles, keep NAT (cheap) and skip the honey container there.

## 6. Ops

* Logs: `/srv/data` volume (`honey.db` + `events.jsonl` + `ssh_host_key`). Back it up.
* fail2ban keeps guarding real sshd (now reached via :2244 redirect; attacker IP preserved).
* Never point fail2ban at the trap (accept-all by design).
* Updates: `docker compose -f docker-compose.prod.yml pull && up -d`.
* History note: 2026-10-08 socket-activation edit bricked server1 SSH
  (`Failed to listen on ssh.socket`); recovered via boot-volume surgery.
  sshd/socket files are henceforth off-limits — steering lives in UFW NAT only.
