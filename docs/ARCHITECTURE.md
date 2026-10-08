# Honey I'm Home — design

## Goals
Deceive automated SSH botnets + manual intruders with believable Ubuntu 22.04/24.04 shell, capture everything needed for intel, show it per-IP in admin UI. Single public port (2222), admin UI never public without SSO.

## Non-goals
No real command execution, no outbound connections, no password cracking, no attribution beyond OSINT (geo/RDAP/rDNS).

## Architecture
```
                  ┌──────────────┐
attacker ──ssh──▶ │ honeypot     │  asyncssh server, fake FS+shell
:2222             │ (backend/app)│──▶ sqlite (sessions, auths, tty, commands)
                  │ honeypot.py  │──▶ data/events.jsonl (source of truth)
                  └──────┬───────┘
                         │ FastAPI :8078 /api/* + serves frontend/dist
                         ▼
                  ┌──────────────┐
admin ──tailnet─▶ │ React UI     │  SSO via edge, JWT direct, mask toggle
+SSO              │ /            │
                  └──────────────┘
```

## Data model (sqlite)
* sessions(id, started_at, ended_at, src_ip, src_port, client_version, kex, cipher, geo_country, geo_city, asn, org, rdns, user_agent_hint)
* auth_attempts(id, session_id, ts, username, password, key_type, fingerprint, key_b64, method, success)
* tty_events(id, session_id, ts_ms, kind[key|output|resize|exec], data, cols, rows)
* commands(id, session_id, ts, username, cwd, command, output_preview)

## Ubuntu emulation details
* Banner: `SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5`. MOTD + `Last login:` with attacker IP.
* Virtual CWD per session, starts `/home/ubuntu`. `cd`, `pwd`, `ls` (static listing), `cat` (fake passwd/shadow deny, fake www config), `echo`, `env`, `history` (seeded).
* `sudo X` → `[sudo] password for user:` → log next line as password → `user is not in the sudoers file.`
* `wget URL` / `curl URL` → extract URL, log, return `Connection refused` / `Failed to connect`.
* `ssh user@host` / `scp ...` → log target, return `Connection timed out`.
* `apt install X` → fake `E: Unable to acquire ...` after 1s delay.
* Timing delays (50-200ms) to feel real. Backspace, Ctrl+C, Ctrl+D, arrows handled minimally.
* Never interpolate attacker input into shell; all output from allowlist templates.

## API auth
* Local admin: `ADMIN_PASSWORD` bcrypt hash at startup, `POST /api/auth/login` → JWT 12h. Roles: `admin`, `viewer` (read-only).
* SSO: trust `X-Forwarded-User` from Authentik/Traefik when `TRUST_PROXY_AUTH=1` + allowlist IP.
* Rate-limit login 5/min/IP. Audit log for logins.

## Frontend pages
1. Overview: totals (sessions, creds, commands, unique IPs), 48h area chart, top users/passwords/countries.
2. Live: WS tail of auth+command events, pause/filter by IP.
3. Attackers: table grouped by IP (flag, city/org/ASN, attempts, users tried, first/last, recon badge), click → drawer with sessions + replay.
4. Replay: terminal player using tty_events timing.
5. Search: filter by user/pass/command/client version.

## Docker
* Single image `ghcr.io/authoritydmc/honey-im-home` + `rajlabs/honey-im-home`: python slim + built React dist. Volumes: `/srv/data`. Ports: `2222` honeypot, `8078` api/ui. `HEALTHCHECK /healthz`.
* Compose: honey service + optional watchtower, traefik labels (`Host(honey.example.com)` → 8078, honeypot TCP router 2222).

## Security / abuse
* Honeypot runs as non-root, no exec, no socket egress (iptables DROP OUTPUT except DNS-less). Resource caps: max 100 concurrent sessions, 60s idle timeout, 5MB/session cap.
* Geo via offline DB preferred (no leak of attacker IP to third party); online enrich opt-in with cache 30d.
* Legal banner in README + UI footer. Retention config `RETENTION_DAYS=90`.

## Roadmap
v0.1 (this scaffold): asyncssh accept-all, fake shell 20 cmds, sqlite, 5 REST endpoints, minimal React tables. v0.2: replay player, geo/ASN, map, WS live. v0.3: SSO, mask, bans export to fail2ban/crowdsec, multi-arch images.
