import { useEffect, useState } from 'react'
import { ShieldAlert } from 'lucide-react'
import { api, fmtAgo, maskVal, type Attempt, type Attacker, type Command, type Session } from '../lib/api'
import { Card, Drawer } from '../components/Drawer'
import { buildTimeline, SessionMeta, Timeline } from '../components/Timeline'

export function Attackers({ token, mask }: { token?: string; mask: boolean }) {
  const [rows, setRows] = useState<Attacker[]>([])
  const [ip, setIp] = useState<string | null>(null)
  useEffect(() => {
    api<Attacker[]>('/api/attackers', token).then(setRows).catch(() => {})
  }, [token])
  return (
    <div className="space-y-3">
      {rows.map(a => (
        <button key={a.ip} onClick={() => setIp(a.ip)} className="w-full text-left">
          <Card className="hover:border-amber-500/40 transition-colors">
            <div className="flex items-center gap-3">
              <ShieldAlert size={18} className="text-amber-400 shrink-0" />
              <span className="mono font-bold flex-1 break-all">{mask ? maskVal(a.ip) : a.ip}</span>
              <span className="text-xs text-zinc-400">{a.sessions} sessions · {a.attempts} attempts</span>
              <span className="text-xs text-zinc-500 hidden sm:inline" title={fmtTime(a.last_seen)}>active {fmtAgo(a.last_seen)}</span>
            </div>
            <div className="mono text-xs text-zinc-500 mt-1 truncate">tried: {a.users || '—'}</div>
          </Card>
        </button>
      ))}
      {rows.length === 0 && <div className="text-sm text-zinc-500 py-6">No attackers recorded yet.</div>}
      {ip && <AttackerDetail ip={ip} token={token} mask={mask} onClose={() => setIp(null)} />}
    </div>
  )
}

export function AttackerDetail({ ip, token, mask, onClose }: { ip: string; token?: string; mask: boolean; onClose: () => void }) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [auths, setAuths] = useState<Attempt[]>([])
  const [cmds, setCmds] = useState<Command[]>([])
  useEffect(() => {
    const q = `ip=${encodeURIComponent(ip)}&limit=100`
    api<Session[]>(`/api/sessions?ip=${encodeURIComponent(ip)}&limit=20`, token).then(setSessions).catch(() => {})
    api<Attempt[]>(`/api/credentials?${q}`, token).then(setAuths).catch(() => {})
    api<Command[]>(`/api/commands?${q}`, token).then(setCmds).catch(() => {})
  }, [ip, token])
  const bySession = new Map(sessions.map(s => [s.id, s]))
  const evs = [
    ...auths.map(a => ({ ts: a.ts, kind: 'auth' as const, title: `${a.method} login as ${a.username} (${a.session_id.slice(0, 8)})`, detail: a.method === 'password' ? `password: ${a.password}` : undefined, secret: a.method === 'password' })),
    ...cmds.map(c => ({ ts: c.ts, kind: 'cmd' as const, title: `${c.command} (${c.session_id.slice(0, 8)})`, detail: c.cwd || undefined })),
  ].sort((x, y) => x.ts - y.ts)
  const first = sessions[sessions.length - 1]
  return (
    <Drawer title={mask ? maskVal(ip) : ip} onClose={onClose}>
      {first && (
        <div className="mb-4"><SessionMeta s={first} mask={mask} /></div>
      )}
      <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wide mb-2">
        Everything this IP did ({sessions.length} sessions)
      </h3>
      <Timeline events={evs} mask={mask} />
      {bySession.size === 0 && evs.length === 0 && <div className="text-sm text-zinc-500">Loading…</div>}
    </Drawer>
  )
}
