import type { ReactNode } from 'react'
import { X } from 'lucide-react'

export function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full max-w-xl bg-zinc-950 border-l border-zinc-800 p-5 overflow-y-auto">
        <div className="flex items-center gap-2 mb-4">
          <h2 className="font-bold text-base flex-1 break-all">{title}</h2>
          <button onClick={onClose} className="p-1.5 rounded bg-zinc-800 hover:bg-zinc-700" aria-label="Close">
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`p-4 rounded-2xl bg-zinc-900 border border-zinc-800/60 ${className}`}>{children}</div>
}

export function Th({ children }: { children: ReactNode }) {
  return <th className="text-left text-xs font-medium text-zinc-500 pb-2 pr-3">{children}</th>
}
