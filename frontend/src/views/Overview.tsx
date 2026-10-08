import { useEffect, useState } from 'react'
import { Activity, KeyRound, TerminalSquare, Globe } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtHour, maskVal, type Stats } from '../lib/api'
import { Card } from '../components/Drawer'

function Bars({ rows, label, value }: { rows: { [k: string]: string | number }[]; label: string; value: string }) {
  const max = Math.max(1, ...rows.map(r => Number(r[value])))
  return (
    <div className="space-y-1.5">
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <span className="mono w-40 shrink-0 truncate text-zinc-300">{String(r[label])}</span>
          <div className="flex-1 h-2 rounded-full bg-zinc-800 overflow-hidden">
            <div className="h-full rounded-full bg-amber-500/80" style={{ width: `${(Number(r[value]) / max) * 100}%` }} />
          </div>
          <span className="mono w-12 text-right text-zinc-400">{r[value]}</span>
        </div>
      ))}
    </div>
  )
}

export function Overview({ token, mask }: { token?: string; mask: boolean }) {
  const [s, setS] = useState<Stats | null>(null)
  useEffect(() => {
    api<Stats>('/api/stats', token).then(setS).catch(() => {})
  }, [token])
  if (!s) return <div className="text-sm text-zinc-500 py-8">Loading intel…</div>
  const cards = [
    { icon: Activity, k: 'Sessions', v: s.sessions },
    { icon: KeyRound, k: 'Auth attempts', v: s.auths },
    { icon: TerminalSquare, k: 'Commands', v: s.commands },
    { icon: Globe, k: 'Attacker IPs', v: s.ips },
  ]
  const tl = s.timeline.map(p => ({ ...p, label: fmtHour(p.h) }))
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {cards.map(c => (
          <Card key={c.k}>
            <div className="flex items-center gap-2 text-xs text-zinc-400"><c.icon size={14} />{c.k}</div>
            <div className="text-3xl font-bold mt-1">{c.v.toLocaleString()}</div>
          </Card>
        ))}
      </div>
      <Card>
        <h2 className="font-bold text-sm mb-2">Auth attempts — last 48h</h2>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={tl} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={{ fill: '#71717a', fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={48} />
              <YAxis tick={{ fill: '#71717a', fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: 8 }} labelStyle={{ color: '#e4e4e7' }} />
              <Area type="monotone" dataKey="n" name="attempts" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.22} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <div className="grid lg:grid-cols-2 gap-3">
        <Card>
          <h2 className="font-bold text-sm mb-3">Top attacker IPs</h2>
          <Bars rows={s.top_ips.map(x => ({ ip: mask ? maskVal(x.src_ip) : x.src_ip, n: x.n }))} label="ip" value="n" />
        </Card>
        <Card>
          <h2 className="font-bold text-sm mb-3">Top usernames tried</h2>
          <Bars rows={s.top_users.map(x => ({ user: mask ? maskVal(x.username) : x.username, n: x.n }))} label="user" value="n" />
        </Card>
      </div>
    </div>
  )
}
