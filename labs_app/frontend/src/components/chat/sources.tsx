import { SourceItem } from '../source_item'
import { SourceType } from 'types'

export type SourcesProps = {
  sources: SourceType[]
  showDisclaimer?: boolean
  onSourceClick: (source: string) => void
}
export const Sources: React.FC<SourcesProps> = ({
  sources,
  showDisclaimer,
  onSourceClick,
}) => {
  if (!sources.length) {
    return null
  }

  return (
    <div className="space-y-3">
      {showDisclaimer && (
        <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-300">
          <strong className="text-blue-200">Kilder:</strong> Klikk for å åpne
          utdraget og se paragrafen i detaljer.
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {sources.map((source) => (
          <SourceItem
            key={source.name}
            name={source.name}
            icon={source.icon}
            onSourceClick={onSourceClick}
          />
        ))}
      </div>
    </div>
  )
}
