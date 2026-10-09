import { useEffect, useState } from 'react'
import { BrainCircuit } from 'lucide-react'
import { api } from '../lib/api'

type Card = {
  intent: string; label: string; note: string; count: number; examples: string[]
}

export function Intent({ mask }: { mask: boolean }) {
  const [cards, setCards] = useState<Card[]>([])
  const [total, setTotal] = useState(0)
  const [profile, setProfile] = useState('')
  useEffect(() => {
    api<{ total: number; intents: Card[]; profile: { note: string } }>('/api/insights')
      .then(j => { setCards(j.intents); setTotal(j.total); setProfile(j.profile?.note ?? '') })
      .catch(() => {})
  }, [])
  const shown = (s: string) => mask ? s.slice(0, 60) + (s.length > 60 ? '…' : '') : s
  return (
    <div className="space-y-3">
      {profile && (
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200">
          {profile}
        </div>
      )}
      <p className="text-xs text-zinc-500">Classified from the last {total} commands attackers ran.</p>
      {cards.map(c => (
        <div key={c.intent} className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="flex items-center gap-2">
            <BrainCircuit size={15} className="text-amber-400" />
            <h3 className="font-semibold text-sm">{c.label}</h3>
            <span className="ml-auto text-[11px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300">×{c.count}</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed">{c.note}</p>
          {c.examples.length > 0 && (
            <div className="mt-2 space-y-1">
              {c.examples.map((e, i) => (
                <pre key={i} className="text-[11px] p-2 rounded bg-black/50 text-zinc-300 overflow-x-auto whitespace-pre-wrap break-all">{shown(e)}</pre>
              ))}
            </div>
          )}
        </div>
      ))}
      {cards.length === 0 && <p className="text-sm text-zinc-500">No attacker commands yet — the trap is waiting.</p>}
    </div>
  )
}
