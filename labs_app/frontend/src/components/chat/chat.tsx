import { AppStatus } from 'store/provider'
import ChatInput from 'components/chat/input'
import { AnswerMessage } from 'components/chat/answer_message'
import { ChatMessageList } from 'components/chat/message_list'
import { ChatMessageType } from 'types'

interface ChatProps {
  status: AppStatus
  messages: ChatMessageType[]
  summary?: ChatMessageType
  onSend: (message: string) => void
  onAbortRequest: () => void
  onSourceClick: (sourceName: string) => void
}

export const Chat: React.FC<ChatProps> = ({
  status,
  messages,
  summary,
  onSend,
  onAbortRequest,
  onSourceClick,
}) => {
  const isStreaming = status === AppStatus.StreamingMessage
  const hasMessages = messages.length > 0

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-lg shadow-blue-950/40">
      <AnswerMessage
        status={status}
        text={summary?.content}
        html={summary?.contentHtml}
        sources={summary?.sources || []}
        onSourceClick={onSourceClick}
      />

      {hasMessages && (
        <div className="mt-10">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
            SAMTALEHISTORIKK
          </h3>
          <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
            <ChatMessageList
              messages={messages}
              isMessageLoading={isStreaming}
              onSourceClick={onSourceClick}
            />
          </div>
        </div>
      )}

      <div className="mt-8 rounded-xl border border-white/10 bg-slate-900/50 p-4">
        <ChatInput
          isMessageLoading={isStreaming}
          onSubmit={onSend}
          onAbortRequest={onAbortRequest}
        />
      </div>
    </div>
  )
}
