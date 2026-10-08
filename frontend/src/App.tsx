import { useEffect, useState } from 'react'
import { api } from './lib/api'

type Stats = { sessions: number; auths: number; commands: number; ips: number;
  top_ips: { src_ip: string; n: number }[]; top_users: { username: string; n: number }[] }

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('honey-token') || '')
  const [pw, setPw] = useState('')
  const [stats, setStats] = useState<Stats | null>(null)
  const [attackers, setAttackers] = useState<any[]>([])
  const [mask, setMask] = useState(true)
  const show = (s: string) => (mask ? s.slice(0, 3) + '…' + s.slice(-2) : s)

  const load = async (t: string) => {
    setStats(await api('/api/stats', t))
    setAttackers(await api('/api/attackers', t))
  }
  useEffect(() => { if (token) load(token).catch(() => setToken('')) }, [token])

  const login = async () => {
    const r = await fetch('/api/auth/login', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pw }) })
    if (!r.ok) return alert('bad password')
    const j = await r.json()
    localStorage.setItem('honey-token', j.token)
    setToken(j.token)
  }

  if (!token) return (
    <div className="min-h-screen grid place-items-center bg-zinc-950 text-zinc-100">
      <div className="p-8 rounded-2xl bg-zinc-900 w-96">
        <h1 className="text-xl font-bold">🍯 Honey I'm Home — admin</h1>
        <input type="password" value={pw} onChange={e => setPw(e.target.value)}
          placeholder="admin password" className="mt-4 w-full p-2 rounded bg-zinc-800" />
        <button onClick={login} className="mt-3 w-full p-2 rounded bg-amber-500 text-black font-bold">Sign in</button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <header className="flex items-center gap-3">
        <h1 className="text-xl font-bold">🍯 Honey I'm Home</h1>
        <span className="text-xs text-zinc-400">Ubuntu SSH trap + intel</span>
        <button onClick={() => setMask(!mask)} className="ml-auto text-xs px-3 py-1 rounded bg-zinc-800">
          {mask ? 'Unmask' : 'Mask'}
        </button>
      </header>
      <div className="grid grid-cols-4 gap-3 mt-4">
        {[['Sessions', stats?.sessions], ['Auths', stats?.auths], ['Commands', stats?.commands], ['IPs', stats?.ips]].map(([k, v]) => (
          <div key={k} className="p-4 rounded-2xl bg-zinc-900"><div className="text-xs text-zinc-400">{k}</div>
            <div className="text-2xl font-bold">{v ?? '…'}</div></div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 mt-4">
        <div className="p-4 rounded-2xl bg-zinc-900">
          <h2 className="font-bold text-sm">Top IPs</h2>
          {stats?.top_ips.map(x => <div key={x.src_ip} className="flex justify-between text-sm py-1">
            <span>{show(x.src_ip)}</span><span>{x.n}</span></div>)}
        </div>
        <div className="p-4 rounded-2xl bg-zinc-900">
          <h2 className="font-bold text-sm">Top users tried</h2>
          {stats?.top_users.map(x => <div key={x.username} className="flex justify-between text-sm py-1">
            <span>{show(x.username)}</span><span>{x.n}</span></div>)}
        </div>
      </div>
      <div className="p-4 rounded-2xl bg-zinc-900 mt-4">
        <h2 className="font-bold text-sm">Attackers by IP</h2>
        <table className="w-full text-sm mt-2">
          <thead className="text-zinc-400"><tr><th className="text-left">IP</th><th>Sessions</th><th>Attempts</th><th>Users</th></tr></thead>
          <tbody>{attackers.map(a => <tr key={a.ip} className="border-t border-zinc-800">
            <td>{show(a.ip)}</td><td>{a.sessions}</td><td>{a.attempts}</td>
            <td className="truncate max-w-64">{a.users}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}
