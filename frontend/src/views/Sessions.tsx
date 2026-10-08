import { useEffect, useState } from 'react'
import { History } from 'lucide-react'
import { api, fmtAgo, fmtTime, maskVal, type Attempt, type Command, type Session } from '../lib/api'
import { Card, Drawer, Th } from '../components/Drawer'
import { buildTimeline, SessionMeta, Timeline } from '../components/Timeline'

export function Sessions({ token, mask }: { token?: string; mask: boolean }) {
  const [rows, setRows] = useState<Session[]>([])
  const [sel, setSel] = useState<Session | null>(null)
  useEffect(() => {
    api<Session[]>('/api/sessions?limit=50', token).then(setRows).catch(() => {})
  }, [token])
  return (
    <div className="space-y-2">
      {rows.map(s => (
        <button key={s.id} onClick={() => setSel(s)} className="w-full text-left">
          <Card className="hover:border-sky-500/40 transition-colors !py-3">
            <div className="flex items-center gap-3 text-sm">
              <History size={15} className="text-sky-400 shrink-0" />
              <span className="mono font-bold break-all">{mask ? maskVal(s.src_ip) : s.src_ip}</span>
              <span className="mono text-xs text-zinc-500">{s.id.slice(0, 8)}</span>
              <span className="ml-auto text-xs text-zinc-500 shrink-0" title={fmtTime(s.started_at)}>{fmtAgo(s.started_at)}</span>
              {!s.ended_at && <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 shrink-0">live</span>}
            </div>
            <div className="mono text-xs text-zinc-500 mt-1 truncate">{s.client_version || 'TCP probe — no handshake'}</div>
          </Card>
        </button>
      ))}
      {rows.length === 0 && <div className="text-sm text-zinc-500 py-6">No sessions yet.</div>}
      {sel && <SessionDetail s={sel} token={token} mask={mask} onClose={() => setSel(null)} />}
    </div>
  )
}

export function SessionDetail({ s, token, mask, onClose }: { s: Session; token?: string; mask: boolean; onClose: () => void }) {
  const [auths, setAuths] = useState<Attempt[]>([])
  const [cmds, setCmds] = useState<Command[]>([])
  useEffect(() => {
    api<Attempt[]>(`/api/credentials?session_id=${s.id}&limit=100`, token).then(setAuths).catch(() => {})
    api<Command[]>(`/api/commands?session_id=${s.id}&limit=200`, token).then(setCmds).catch(() => {})
  }, [s.id, token])
  return (
    <Drawer title={`Session ${s.id.slice(0, 8)} · ${mask ? maskVal(s.src_ip) : s.src_ip}`} onClose={onClose}>
      <div className="mb-4"><SessionMeta s={s} mask={mask} /></div>
      <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wide mb-2">
        Timeline — everything this session did
      </h3>
      <Timeline events={buildTimeline(s, auths, cmds)} mask={mask} />
    </Drawer>
  )
}
