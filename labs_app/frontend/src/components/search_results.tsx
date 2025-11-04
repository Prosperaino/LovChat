import React from 'react'
import { ReactComponent as LightBulb } from 'images/light_bulb_icon.svg'
import { SourceType } from '../types'
import { SearchResult } from './search_result'

interface SearchResultsProps {
  results: SourceType[]
  toggleSource: (source: string) => void
}

export const SearchResults: React.FC<SearchResultsProps> = ({
  results,
  toggleSource,
}) => {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-lg shadow-blue-950/30">
      <header className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/10 text-blue-200">
          <LightBulb width={20} height={20} />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-white">Kilder fra Lovdata</h2>
          <p className="text-xs text-slate-400">
            Klikk for å lese utdragene og åpne lenken til lovteksten.
          </p>
        </div>
      </header>

      {results?.length ? (
        <div className="mt-5 space-y-3">
          {results.map((result) => (
            <SearchResult
              key={result.name}
              toggleSource={toggleSource}
              {...result}
            />
          ))}
        </div>
      ) : (
        <p className="mt-6 text-sm text-slate-400">
          Når du stiller et spørsmål henter vi relevante paragrafer, forarbeider
          og andre kilder fra Lovdata. De vises her så snart de er funnet.
        </p>
      )}
    </section>
  )
}
