import React, { MouseEvent } from 'react'
import { plainTextToHtml, sanitizeModelText } from 'lib/utils'
import { SourceIcon } from './source_icon'
import { SourceType } from '../types'
import { ReactComponent as ArrowDown } from 'images/chevron_down_icon.svg'

interface SearchResultProps extends SourceType {
  toggleSource: (source: string) => void
}

const formatUpdatedAt = (value?: string | null) => {
  if (!value) {
    return null
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }

  const formatted = date.toLocaleDateString('nb-NO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

  return `Oppdatert ${formatted}`
}

export const SearchResult: React.FC<SearchResultProps> = ({
  name,
  icon,
  url,
  source_path,
  summary,
  updated_at,
  expanded = false,
  toggleSource,
}) => {
  const linkTarget = url || source_path || ''
  const updatedLabel = formatUpdatedAt(updated_at)
  const summaries = summary ?? []
  const renderedSummaries = summaries
    .map((text, index) => ({
      index,
      html: plainTextToHtml(sanitizeModelText(text)),
    }))
    .filter(({ html }) => html.length > 0)

  const handleToggle = (event: MouseEvent<HTMLButtonElement>) => {
    const target = event.target as HTMLElement
    if (target.closest('a')) {
      return
    }

    toggleSource(name)
  }

  return (
    <article
      className="overflow-hidden rounded-xl border border-white/10 bg-white/5 text-slate-200 transition hover:border-blue-400/50 hover:bg-blue-500/10"
      data-source={name}
    >
      <button
        type="button"
        onClick={handleToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div className="flex flex-1 items-center gap-3">
          <SourceIcon
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/10 text-sm font-semibold text-slate-200"
            icon={icon}
          />
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-semibold text-white md:text-base">
              {name}
            </h3>
            {linkTarget && (
              <p className="truncate text-xs text-blue-200/80">
                {linkTarget}
              </p>
            )}
          </div>
        </div>
        <ArrowDown
          className={`h-4 w-4 flex-shrink-0 text-slate-300 transition ${
            expanded ? 'rotate-180' : ''
          }`}
        />
      </button>

      <div
        className={`grid transition-all duration-300 ${
          expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
        }`}
      >
        <div className="overflow-hidden border-t border-white/10 px-4 pb-4 pt-3 text-sm text-slate-200">
          {linkTarget ? (
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-white/10 bg-white/10 px-2 py-0.5 text-[11px] uppercase tracking-widest text-slate-300">
                Lenke
              </span>
              <a
                className="inline-flex items-center gap-2 text-sm font-medium text-blue-200 underline decoration-dotted underline-offset-4 hover:text-white"
                target="_blank"
                rel="noreferrer"
                href={linkTarget}
              >
                Åpne i Lovdata
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-3.5 w-3.5"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path d="M13 3a1 1 0 110 2H8a1 1 0 000 2h3.586l-5.793 5.793a1 1 0 101.414 1.414L13 8.414V12a1 1 0 102 0V5a2 2 0 00-2-2h-5z" />
                  <path d="M5 7a2 2 0 00-2 2v6a2 2 0 002 2h6a2 2 0 002-2v-1a1 1 0 10-2 0v1H5V9h1a1 1 0 000-2H5z" />
                </svg>
              </a>
            </div>
          ) : (
            <p className="mb-4 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400">
              Lenke ikke tilgjengelig for denne kilden.
            </p>
          )}

          {renderedSummaries.length > 0 && (
            <div className="space-y-3">
              {renderedSummaries.map(({ index, html }) => (
                <div
                  key={`${name}-${index}`}
                  className="rounded-lg border border-white/10 bg-slate-950/40 px-3 py-3 text-sm leading-relaxed text-slate-100 shadow-inner shadow-slate-950/40 [&>p]:mb-2 [&>p:last-child]:mb-0"
                  dangerouslySetInnerHTML={{ __html: html }}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {updatedLabel && (
        <footer className="border-t border-white/5 bg-white/5 px-4 py-2 text-right text-[11px] uppercase tracking-widest text-slate-400">
          {updatedLabel}
        </footer>
      )}
    </article>
  )
}
