# Honey I'm Home 🍯🏠 — Ubuntu-style SSH Honeypot + SOC Dashboard

Fake Ubuntu SSH server with full emulation + keylogging, backed by FastAPI + SQLite and a React admin UI. For security research on systems you own.

> ⚠️ Legal: deploy only on hosts you own / are authorized to test. Logs attacker IPs, credentials, keystrokes, commands, SSH client fingerprints. No reference to any upstream project — original build.

```
attacker --ssh--> honeypot :2222 --events--> sqlite --FastAPI :8078--> React dashboard
```

## Quickstart

```bash
git clone https://github.com/authoritydmc/honey-im-home && cd honey-im-home
cp .env.example .env  # set ADMIN_PASSWORD, SECRET_KEY
docker compose up -d --build
# honeypot on :2222, dashboard+API on :8078
curl -s localhost:8078/healthz  # -> ok
```

Single image also published:

```bash
docker run -d --name honey-im-home --restart unless-stopped \
  -p 2222:2222 -p 8078:8078 \
  -e ADMIN_PASSWORD=change-me -e SECRET_KEY=change-me \
  -v honey_data:/srv/data \
  ghcr.io/authoritydmc/honey-im-home:latest
```

## What it captures

* Session: src IP/port, reverse DNS, Geo/ASN/org (cached), SSH client version, kex/ciphers, first/last seen
* Auth: every username/password, key type + fingerprint + base64, keyboard-interactive, auth order
* TTY: per-keystroke timing, window-size changes, PTY type, exec vs shell, `scp/sftp` attempts
* Commands: full line + fake Ubuntu output, `sudo` password prompts, `wget/curl` URLs, lateral `ssh` attempts
* Replay: timing file to replay session in UI terminal player

## Ubuntu emulation

Banner `SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5`, fake FS (`/home/ubuntu`, `/etc/passwd`, `/var/www`), commands: `whoami id pwd hostname uname uptime ls cat echo cd env history ps ifconfig ip netstat ss wget curl apt sudo ssh scp exit clear`. Unknown commands return `bash: X: command not found`. `sudo` always denies + logs password. `wget/curl` log URL then `Connection refused`.

## API

* `GET /healthz` → ok
* `POST /api/auth/login` → JWT (admin)
* `GET /api/stats` → totals, top IPs/users/countries, 48h timeline
* `GET /api/sessions?ip=&limit=` → sessions with replay
* `GET /api/credentials`, `GET /api/commands`, `GET /api/attackers` → grouped by IP with geo
* `WS /api/live` → new events tail
* All `/api/*` (except login/healthz) require `Authorization: Bearer <jwt>` or Traefik ForwardAuth header.

## Frontend

React 19 + Vite + Tailwind. Pages: Overview (totals, 48h chart, top IPs), Live (websocket tail), Attackers (by IP: geo/ASN, users tried, sessions, replay button), Session replay (xterm-style player), Credentials/Commands tables. Header mask toggle hides sensitive values. Base path `/honey/`.

## Layout

```
backend/          FastAPI + asyncssh honeypot + sqlite
frontend/         Vite React dashboard (built to backend/static)
data/             sqlite + jsonl (volume)
docs/ARCHITECTURE.md  design + data model + procedures
```

## Ops

* Healthcheck on `/healthz`, JSONL remains source of truth, SQLite derived.
* Behind Traefik: keep `2222` public for attackers, keep `8078` on tailnet + SSO (Authentik) for admins.
* See `docs/ARCHITECTURE.md` for threat model, resource limits, backup.
