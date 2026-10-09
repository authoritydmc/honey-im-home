import { useEffect, useState } from 'react'
import { Activity, BrainCircuit, Eye, EyeOff, KeyRound, LayoutDashboard, ListOrdered, LogIn, Radio, ShieldAlert, ShieldCheck, TerminalSquare } from 'lucide-react'
import { api, type AuthStatus } from './lib/api'
import { Overview } from './views/Overview'
import { Live } from './views/Live'
import { Attackers } from './views/Attackers'
import { Sessions } from './views/Sessions'
import { Commands, Credentials } from './views/Intel'
import { Intent } from './views/Intent'

type Tab = 'overview' | 'intent' | 'live' | 'attackers' | 'sessions' | 'creds' | 'cmds'

const TABS: { id: Tab; label: string; icon: typeof Activity }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'intent', label: 'Intent', icon: BrainCircuit },
  { id: 'live', label: 'Live', icon: Radio },
  { id: 'attackers', label: 'Attackers', icon: ShieldAlert },
  { id: 'sessions', label: 'Sessions', icon: ListOrdered },
  { id: 'creds', label: 'Credentials', icon: KeyRound },
  { id: 'cmds', label: 'Commands', icon: TerminalSquare },
]

export default function App() {
  const [proxyUser, setProxyUser] = useState<string | null>(null)
  const [authUrl, setAuthUrl] = useState('')
  const [tab, setTab] = useState<Tab>('overview')
  const [mask, setMask] = useState(true)
  const [booted, setBooted] = useState(false)

  useEffect(() => {
    // SSO-only: the edge (Traefik ForwardAuth -> Authentik) injects identity.
    // No app password exists. If no identity header is present the user is
    // not signed in at the edge -> show the SSO sign-in button.
    const boot = async () => {
      try {
        const a = await api<AuthStatus & { auth_url?: string }>('/api/auth')
        if (a.mode === 'sso' && a.user) { setProxyUser(a.user); return }
        if (a.auth_url) setAuthUrl(a.auth_url)
      } catch { /* backend unreachable */ }
      setBooted(true)
    }
    boot().finally(() => setBooted(true))
  }, [])

  if (!proxyUser && booted) {
    return (
      <div className="min-h-screen grid place-items-center bg-zinc-950 text-zinc-100 p-4">
        <div className="p-8 rounded-2xl bg-zinc-900 border border-zinc-800 w-96 max-w-full text-center">
          <h1 className="text-xl font-bold">🍯 Honey I'm Home</h1>
          <p className="text-xs text-zinc-500 mt-1 flex items-center justify-center gap-1">
            <ShieldCheck size={13} /> Protected by RajLabs SSO — no app password
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-5 w-full p-2.5 rounded-lg bg-amber-500 text-black font-bold flex items-center justify-center gap-2 hover:bg-amber-400">
            <LogIn size={16} /> Sign in with SSO
          </button>
          <p className="text-[11px] text-zinc-500 mt-3">
            Sign-in is handled by {authUrl ? <a className="underline" href={authUrl}>{authUrl}</a> : 'RajLabs SSO (Authentik)'} at the edge.
          </p>
        </div>
      </div>
    )
  }
  if (!proxyUser) return <div className="min-h-screen grid place-items-center text-sm text-zinc-500">Loading trap intel…</div>

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-30 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <h1 className="font-bold">🍯 Honey I'm Home</h1>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">SSO · {proxyUser}</span>
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
        {tab === 'overview' && <Overview mask={mask} />}
        {tab === 'intent' && <Intent mask={mask} />}
        {tab === 'live' && <Live mask={mask} />}
        {tab === 'attackers' && <Attackers mask={mask} />}
        {tab === 'sessions' && <Sessions mask={mask} />}
        {tab === 'creds' && <Credentials mask={mask} />}
        {tab === 'cmds' && <Commands mask={mask} />}
      </main>
    </div>
  )
}
