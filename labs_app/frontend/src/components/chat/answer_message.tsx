import { plainTextToHtml, sanitizeModelText } from 'lib/utils'
import { Sources } from './sources'
import { ChatMessageType } from '../../types'
import { AppStatus } from 'store/provider'

interface AnswerMessageProps {
  text?: ChatMessageType['content']
  html?: ChatMessageType['contentHtml']
  sources: ChatMessageType['sources']
  onSourceClick: (source: string) => void
  status: AppStatus
}

export const AnswerMessage: React.FC<AnswerMessageProps> = ({
  text,
  html,
  sources,
  onSourceClick,
  status,
}) => {
  const sanitized = sanitizeModelText(text || '')
  const renderedHtml = html || plainTextToHtml(sanitized)
  const isLoading = status === AppStatus.StreamingMessage

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-blue-200">
            Svar
            {isLoading && (
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/80 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-300" />
              </span>
            )}
          </div>
          <h2 className="mt-3 text-2xl font-semibold text-white">
            {isLoading ? 'Utformer svar…' : 'Svar fra GPTLov'}
          </h2>
          <p className="mt-1 text-sm text-slate-300">
            Hvert avsnitt er støttet av kilder fra Lovdata.
          </p>
        </div>
      </header>

      <div className="rounded-xl border border-white/10 bg-slate-900/40 p-6 text-base leading-relaxed text-slate-100 shadow-inner shadow-slate-900/40">
        {renderedHtml ? (
          <div
            className="answer-content space-y-4 [&>ol]:list-decimal [&>ol]:pl-6 [&>p]:leading-relaxed [&>p]:text-slate-100 [&>p]:opacity-90 [&>strong]:text-white [&>ul]:list-disc [&>ul]:pl-6"
            dangerouslySetInnerHTML={{ __html: renderedHtml }}
          />
        ) : (
          <div className="space-y-3">
            <div className="h-4 w-3/4 animate-pulse rounded bg-white/10" />
            <div className="h-4 w-11/12 animate-pulse rounded bg-white/10" />
            <div className="h-4 w-5/6 animate-pulse rounded bg-white/10" />
          </div>
        )}
      </div>

      {!!sources?.length && (
        <Sources
          showDisclaimer
          sources={sources}
          onSourceClick={onSourceClick}
        />
      )}
    </div>
  )
}
