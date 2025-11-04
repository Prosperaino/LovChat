import React from 'react'
import { SourceIcon } from './source_icon'

export type SourceProps = {
  name: string
  icon?: string
  onSourceClick: (sourceName: string) => void
}

export const SourceItem: React.FC<SourceProps> = ({
  name,
  icon,
  onSourceClick,
}) => (
  <button
    type="button"
    onClick={() => {
      onSourceClick(name)
    }}
    className="group flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-slate-200 transition hover:-translate-y-0.5 hover:border-blue-400/60 hover:bg-blue-500/15 hover:text-white"
  >
    <SourceIcon
      className="flex h-7 w-7 items-center justify-center rounded-md bg-white/10 text-xs uppercase tracking-wide text-slate-300 group-hover:bg-white/20"
      icon={icon}
    />
    <span className="text-left">
      {name}
    </span>
  </button>
)
