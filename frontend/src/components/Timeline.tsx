import { KeyRound, Terminal, LogIn, LogOut, Fingerprint } from 'lucide-react'
import type { Attempt, Command, Session } from '../lib/api'
import { fmtTime, maskVal } from '../lib/api'

export type TEvent = {
  ts: number
  kind: 'open' | 'auth' | 'cmd' | 'close'
  title: string
  detail?: string
  secret?: boolean
}

export function buildTimeline(s: Session, auths: Attempt[], cmds: Command[]): TEvent[] {
  const evs: TEvent[] = [
    { ts: s.started_at, kind: 'open', title: 'Session opened', detail: s.client_version || undefined },
  ]
  for (const a of auths) {
    if (a.method === 'password') {
      evs.push({ ts: a.ts, kind: 'auth', title: `password login as ${a.username}`, detail: `password: ${a.password}`, secret: true })
    } else if (a.method === 'publickey') {
      evs.push({ ts: a.ts, kind: 'auth', title: `key login as ${a.username}`, detail: a.fingerprint ? `fingerprint: ${a.fingerprint}` : undefined })
    } else {
      evs.push({ ts: a.ts, kind: 'auth', title: `${a.method} login as ${a.username}` })
    }
  }
  for (const c of cmds) evs.push({ ts: c.ts, kind: 'cmd', title: c.command, detail: c.cwd || undefined })
  if (s.ended_at) evs.push({ ts: s.ended_at, kind: 'close', title: 'Session closed' })
  evs.sort((x, y) => x.ts - y.ts)
  return evs
}

const ICONS = {
  open: { C: LogIn, cls: 'bg-sky-500/15 text-sky-400' },
  auth: { C: KeyRound, cls: 'bg-amber-500/15 text-amber-400' },
  cmd: { C: Terminal, cls: 'bg-zinc-500/15 text-zinc-300' },
  close: { C: LogOut, cls: 'bg-zinc-700/30 text-zinc-500' },
}

export function Timeline({ events, mask }: { events: TEvent[]; mask: boolean }) {
  if (events.length === 0) return <div className="text-sm text-zinc-500 py-4">No events recorded yet.</div>
  return (
    <ol className="relative ml-2 border-l border-zinc-800 pl-0">
      {events.map((e, i) => {
        const { C, cls } = ICONS[e.kind]
        return (
          <li key={`${e.ts}-${i}`} className="relative pl-10 pb-5">
            <span className={`absolute left-0 top-0 -translate-x-1/2 rounded-full p-1.5 ${cls}`}>
              <C size={14} />
            </span>
            <div className="text-sm text-zinc-100 break-all">{e.title}</div>
            {e.detail && (
              <div className="mono text-xs text-zinc-400 break-all">
                {e.secret && mask ? maskVal(e.detail) : e.detail}
              </div>
            )}
            <div className="text-xs text-zinc-500" title={fmtTime(e.ts)}>{fmtTime(e.ts)}</div>
          </li>
        )
      })}
    </ol>
  )
}

export function SessionMeta({ s, mask }: { s: Session; mask: boolean }) {
  const rows: [string, string][] = [
    ['Source', mask ? maskVal(s.src_ip) : s.src_ip],
    ['Port', String(s.src_port)],
    ['Client', s.client_version || '— (TCP probe, no handshake)'],
    ['Geo', [s.geo_city, s.geo_country].filter(Boolean).join(', ') || '—'],
    ['ASN / org', [s.asn, s.org].filter(Boolean).join(' · ') || '—'],
  ]
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="flex gap-2">
          <dt className="text-zinc-500 w-16 shrink-0">{k}</dt>
          <dd className="mono text-zinc-200 break-all flex items-center gap-1">
            {k === 'Source' ? <Fingerprint size={12} className="text-zinc-500" /> : null}{v}
          </dd>
        </div>
      ))}
    </dl>
  )
}
