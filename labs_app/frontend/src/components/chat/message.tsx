import React from 'react'
import { ChatMessageType } from 'types'
import { Loader } from 'components/loader'
import { Sources } from 'components/chat/sources'
import { ReactComponent as UserLogo } from 'images/user.svg'
import { ReactComponent as ElasticLogo } from 'images/elastic_logo.svg'
import { plainTextToHtml, sanitizeModelText } from 'lib/utils'

type ChatMessageProps = Omit<ChatMessageType, 'id'> & {
  onSourceClick: (source: string) => void
}

const AssistantBadge = () => (
  <span className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/10 shadow">
    <ElasticLogo width={20} height={20} />
  </span>
)

const UserBadge = () => (
  <span className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-blue-500/40 text-white shadow">
    <UserLogo width={20} height={20} />
  </span>
)

export const ChatMessage: React.FC<ChatMessageProps> = ({
  content,
  contentHtml,
  isHuman,
  sources,
  loading,
  onSourceClick,
}) => {
  const badge = isHuman ? <UserBadge /> : <AssistantBadge />
  const sanitized = sanitizeModelText(content || '')
  const renderedHtml = contentHtml || plainTextToHtml(sanitized)

  return (
    <article className="space-y-3">
      <div
        className={`flex gap-3 ${
          isHuman ? 'flex-row-reverse items-start text-right' : 'items-start'
        }`}
      >
        {badge}
        <div
          className={`max-w-[32rem] rounded-2xl px-5 py-4 text-sm leading-relaxed shadow ${
            isHuman
              ? 'bg-gradient-to-r from-blue-500/90 to-blue-400/90 text-white shadow-blue-900/40'
              : 'border border-white/10 bg-white/5 text-slate-100 shadow-blue-950/10'
          }`}
        >
          {renderedHtml ? (
            <div
              className="space-y-3 [&>ol]:list-decimal [&>ol]:pl-5 [&>p]:leading-relaxed [&>p]:text-current [&>strong]:font-semibold [&>ul]:list-disc [&>ul]:pl-5"
              dangerouslySetInnerHTML={{ __html: renderedHtml }}
            />
          ) : (
            <div className="space-y-2">
              <div className="h-3.5 w-5/6 animate-pulse rounded bg-white/20" />
              <div className="h-3.5 w-4/6 animate-pulse rounded bg-white/20" />
              <div className="h-3.5 w-2/3 animate-pulse rounded bg-white/20" />
            </div>
          )}
          {loading && (
            <Loader className="mt-3 flex justify-end text-white opacity-80" />
          )}
        </div>
      </div>

      {!!sources?.length && (
        <div
          className={`flex gap-3 ${
            isHuman ? 'flex-row-reverse text-right' : ''
          }`}
        >
          {badge}
          <Sources sources={sources || []} onSourceClick={onSourceClick} />
        </div>
      )}
    </article>
  )
}
