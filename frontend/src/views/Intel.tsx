import { useEffect, useState } from 'react'
import { KeyRound, TerminalSquare } from 'lucide-react'
import { api, fmtTime, fmtAgo, maskVal, type Attempt, type Command } from '../lib/api'
import { Card, Th } from '../components/Drawer'

export function Credentials({ token, mask }: { token?: string; mask: boolean }) {
  const [rows, setRows] = useState<Attempt[]>([])
  useEffect(() => {
    api<Attempt[]>('/api/credentials?limit=100', token).then(setRows).catch(() => {})
  }, [token])
  return (
    <Card>
      <h2 className="font-bold text-sm mb-3 flex items-center gap-2"><KeyRound size={15} className="text-amber-400" />Captured credentials</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr><Th>When</Th><Th>IP</Th><Th>User</Th><Th>Secret</Th><Th>Method</Th></tr></thead>
          <tbody>
            {rows.map((a, i) => (
              <tr key={i} className="border-t border-zinc-800">
                <td className="py-1.5 pr-3 text-xs text-zinc-500 whitespace-nowrap" title={fmtTime(a.ts)}>{fmtAgo(a.ts)}</td>
                <td className="mono py-1.5 pr-3 break-all">{mask ? maskVal(a.ip ?? '') : (a.ip || '—')}</td>
                <td className="mono py-1.5 pr-3 break-all">{mask ? maskVal(a.username) : a.username}</td>
                <td className="mono py-1.5 pr-3 break-all text-amber-300/90">
                  {a.method === 'password' ? (mask ? maskVal(a.password, 1) : a.password) : (mask ? maskVal(a.fingerprint ?? '', 6) : (a.fingerprint || '—'))}
                </td>
                <td className="py-1.5 pr-3 text-xs text-zinc-400">{a.method}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <div className="text-sm text-zinc-500 py-4">Nothing captured yet.</div>}
    </Card>
  )
}

export function Commands({ token, mask }: { token?: string; mask: boolean }) {
  const [rows, setRows] = useState<Command[]>([])
  useEffect(() => {
    api<Command[]>('/api/commands?limit=100', token).then(setRows).catch(() => {})
  }, [token])
  return (
    <Card>
      <h2 className="font-bold text-sm mb-3 flex items-center gap-2"><TerminalSquare size={15} className="text-zinc-300" />Attacker commands</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr><Th>When</Th><Th>IP</Th><Th>User</Th><Th>Command</Th></tr></thead>
          <tbody>
            {rows.map((c, i) => (
              <tr key={i} className="border-t border-zinc-800">
                <td className="py-1.5 pr-3 text-xs text-zinc-500 whitespace-nowrap" title={fmtTime(c.ts)}>{fmtAgo(c.ts)}</td>
                <td className="mono py-1.5 pr-3 break-all">{mask ? maskVal(c.ip ?? '') : (c.ip || '—')}</td>
                <td className="mono py-1.5 pr-3 break-all">{mask ? maskVal(c.username) : c.username}</td>
                <td className="mono py-1.5 pr-3 break-all text-zinc-100">{mask ? maskVal(c.command, 24) : c.command}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <div className="text-sm text-zinc-500 py-4">Nothing captured yet.</div>}
    </Card>
  )
}
