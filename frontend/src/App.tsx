import { useEffect, useState } from 'react'
import { Activity, Eye, EyeOff, KeyRound, LayoutDashboard, ListOrdered, Radio, ShieldAlert, TerminalSquare } from 'lucide-react'
import { api, type AuthStatus } from './lib/api'
import { Overview } from './views/Overview'
import { Live } from './views/Live'
import { Attackers } from './views/Attackers'
import { Sessions } from './views/Sessions'
import { Commands, Credentials } from './views/Intel'

type Tab = 'overview' | 'live' | 'attackers' | 'sessions' | 'creds' | 'cmds'

const TABS: { id: Tab; label: string; icon: typeof Activity }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'live', label: 'Live', icon: Radio },
  { id: 'attackers', label: 'Attackers', icon: ShieldAlert },
  { id: 'sessions', label: 'Sessions', icon: ListOrdered },
  { id: 'creds', label: 'Credentials', icon: KeyRound },
  { id: 'cmds', label: 'Commands', icon: TerminalSquare },
]

export default function App() {
  const [token, setToken] = useState('')
  const [proxyUser, setProxyUser] = useState<string | null>(null)
  const [pw, setPw] = useState('')
  const [tab, setTab] = useState<Tab>('overview')
  const [mask, setMask] = useState(true)
  const [booted, setBooted] = useState(false)

  useEffect(() => {
    // Behind the auth proxy the edge injects identity: no token needed.
    // Token login is only for direct, no-proxy access.
    const boot = async () => {
      try {
        const a = await api<AuthStatus>('/api/auth')
        if (a.mode === 'sso' && a.user) { setProxyUser(a.user); return }
      } catch { /* not proxied, fall through */ }
      const t = localStorage.getItem('honey-token')
      if (t) {
        try { setToken(t); await api('/api/stats', t); return }
        catch { localStorage.removeItem('honey-token'); setToken('') }
      }
      setBooted(true)
    }
    boot().finally(() => setBooted(true))
  }, [])

  const authed = proxyUser !== null || token !== ''
  const effToken = token || undefined

  const login = async () => {
    const r = await fetch('/api/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pw }),
    })
    if (!r.ok) return alert('bad password')
    const j = await r.json() as { token: string }
    localStorage.setItem('honey-token', j.token)
    setToken(j.token)
  }

  if (!authed && booted) {
    return (
      <div className="min-h-screen grid place-items-center bg-zinc-950 text-zinc-100 p-4">
        <div className="p-8 rounded-2xl bg-zinc-900 border border-zinc-800 w-96 max-w-full">
          <h1 className="text-xl font-bold">🍯 Honey I'm Home</h1>
          <p className="text-xs text-zinc-500 mt-1">Sign in — not needed behind SSO</p>
          <input type="password" value={pw} onChange={e => setPw(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') login() }}
            placeholder="admin password" className="mt-4 w-full p-2 rounded bg-zinc-800 outline-none focus:ring-1 focus:ring-amber-500" />
          <button onClick={login} className="mt-3 w-full p-2 rounded bg-amber-500 text-black font-bold">Sign in</button>
        </div>
      </div>
    )
  }
  if (!authed) return <div className="min-h-screen grid place-items-center text-sm text-zinc-500">Loading trap intel…</div>

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <h1 className="font-bold">🍯 Honey I'm Home</h1>
          {proxyUser
            ? <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">SSO · {proxyUser}</span>
            : <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400">token</span>}
          <button onClick={() => setMask(!mask)} className="ml-auto flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700">
            {mask ? <EyeOff size={14} /> : <Eye size={14} />}{mask ? 'Masked' : 'Visible'}
          </button>
        </div>
        <nav className="max-w-6xl mx-auto px-4 pb-2 flex gap-1 overflow-x-auto">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg whitespace-nowrap ${tab === t.id ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-900'}`}>
              <t.icon size={15} />{t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-4">
        {tab === 'overview' && <Overview token={effToken} mask={mask} />}
        {tab === 'live' && <Live mask={mask} />}
        {tab === 'attackers' && <Attackers token={effToken} mask={mask} />}
        {tab === 'sessions' && <Sessions token={effToken} mask={mask} />}
        {tab === 'creds' && <Credentials token={effToken} mask={mask} />}
        {tab === 'cmds' && <Commands token={effToken} mask={mask} />}
      </main>
    </div>
  )
}
