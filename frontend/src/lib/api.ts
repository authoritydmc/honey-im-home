export type Stats = {
  sessions: number; auths: number; commands: number; ips: number;
  top_ips: { src_ip: string; n: number }[];
  top_users: { username: string; n: number }[];
  timeline: { h: number; n: number }[];
}

export type Session = {
  id: string; started_at: number; ended_at: number | null;
  src_ip: string; src_port: number; client_version: string;
  geo_country: string | null; geo_city: string | null;
  asn: string | null; org: string | null;
}

export type Attempt = {
  session_id: string; ts: number; username: string; password: string;
  method: string; success: number; fingerprint?: string; ip?: string;
}

export type Command = {
  session_id: string; ts: number; username: string; cwd: string;
  command: string; ip?: string;
}

export type Attacker = {
  ip: string; sessions: number; attempts: number;
  first_seen: number; last_seen: number; users: string | null;
}

export type AuthStatus = { mode: string; login: string; user: string | null }

export async function api<T>(path: string, token?: string): Promise<T> {
  const r = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json() as Promise<T>
}

export function fmtTime(ts: number | null): string {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
}

export function fmtHour(h: number): string {
  return new Date(h * 1000).toLocaleString(undefined, { month: 'numeric', day: 'numeric', hour: '2-digit' })
}

export function fmtAgo(ts: number | null): string {
  if (!ts) return '—'
  const s = Math.max(0, Date.now() / 1000 - ts)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

/** Screenshot-safe masking: IPs, usernames, passwords hidden until unmasked. */
export function maskVal(s: string | null | undefined, keep = 3): string {
  if (s === null || s === undefined) return '—'
  if (s.length <= keep + 2) return '•••'
  return `${s.slice(0, keep)}…${s.slice(-2)}`
}
