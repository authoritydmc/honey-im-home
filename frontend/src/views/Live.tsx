import { useEffect, useState } from 'react'
import { KeyRound, LogIn, LogOut, Radio, Terminal } from 'lucide-react'
import { fmtTime, maskVal } from '../lib/api'
import { Card } from '../components/Drawer'

type Ev = { type: string; ip?: string; user?: string; cmd?: string; method?: string; ts: number; id?: string; client?: string }

function iconFor(t: string) {
  if (t === 'auth') return <KeyRound size={14} className="text-amber-400" />
  if (t === 'cmd') return <Terminal size={14} className="text-zinc-300" />
  if (t === 'session.open') return <LogIn size={14} className="text-sky-400" />
  if (t === 'session.close') return <LogOut size={14} className="text-zinc-500" />
  return <Radio size={14} className="text-zinc-500" />
}

function textFor(e: Ev, mask: boolean): string {
  const ip = e.ip ? (mask ? maskVal(e.ip) : e.ip) : ''
  if (e.type === 'auth') return `${ip} tried ${e.method} login as ${mask ? maskVal(e.user ?? '') : e.user}`
  if (e.type === 'cmd') return `${ip} ran: ${mask ? maskVal(e.cmd ?? '', 12) : e.cmd}`
  if (e.type === 'session.open') return `${ip} connected${e.client ? ` (${e.client.slice(0, 28)})` : ''}`
  if (e.type === 'session.close') return `${ip} disconnected`
  return JSON.stringify(e).slice(0, 120)
}

export function Live({ mask }: { mask: boolean }) {
  const [evs, setEvs] = useState<Ev[]>([])
  const [on, setOn] = useState(false)
  useEffect(() => {
    let ws: WebSocket | null = null
    try {
      ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/live`)
    } catch { return }
    ws.onopen = () => setOn(true)
    ws.onmessage = m => {
      try {
        const e = JSON.parse(m.data) as Ev
        setEvs(prev => [e, ...prev].slice(0, 150))
      } catch { /* ignore malformed frames */ }
    }
    ws.onclose = () => setOn(false)
    return () => ws?.close()
  }, [])
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm">
        <span className={`inline-block w-2 h-2 rounded-full ${on ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'}`} />
        <span className="text-zinc-400">{on ? 'Live — streaming attacker events' : 'Connecting…'}</span>
      </div>
      {evs.length === 0 && <div className="text-sm text-zinc-500 py-6">Waiting for the next knock on the trap…</div>}
      {evs.map((e, i) => (
        <Card key={`${e.ts}-${i}`} className="!py-2.5">
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5">{iconFor(e.type)}</span>
            <div className="flex-1 min-w-0">
              <div className="text-sm text-zinc-100 break-all">{textFor(e, mask)}</div>
              <div className="text-xs text-zinc-500" title={fmtTime(e.ts)}>{fmtTime(e.ts)}</div>
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}
