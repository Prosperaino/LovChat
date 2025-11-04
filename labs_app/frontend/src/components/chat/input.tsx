import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import autosize from 'autosize'
import Conversation from 'images/conversation'
import { ReactComponent as SendIcon } from 'images/paper_airplane_icon.svg'
import { ReactComponent as StopIcon } from 'images/stop_icon.svg'

type ChatInputProps = {
  isMessageLoading: boolean
  onSubmit: (value: string) => void
  onAbortRequest: () => void
}

export default function ChatInput({
  isMessageLoading,
  onSubmit,
  onAbortRequest,
}: ChatInputProps) {
  const [message, setMessage] = useState<string>('')
  const textareaReference = useRef<HTMLTextAreaElement>(null)

  const trimmedMessage = message.trim()
  const isSubmitDisabled = !trimmedMessage.length || isMessageLoading

  const handleSubmit = (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault()

    if (!isSubmitDisabled) {
      onSubmit(trimmedMessage)
      setMessage('')
      const textarea = textareaReference.current
      if (textarea) {
        textarea.style.height = ''
        autosize.update(textarea)
      }
    }
  }

  const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const textarea = textareaReference.current
    if (textarea) {
      textarea.style.height = ''
      autosize.update(textarea)
    }
    setMessage(event.target.value)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit()
    }
  }

  useLayoutEffect(() => {
    const ref = textareaReference.current

    ref?.focus()
    autosize(ref)

    return () => {
      autosize.destroy(ref)
    }
  }, [])

  return (
    <form className="space-y-3" onSubmit={handleSubmit}>
      <div className="relative overflow-hidden rounded-xl border border-white/10 bg-slate-950/60 shadow-inner shadow-black/40 focus-within:border-blue-400/60 focus-within:shadow-blue-500/20">
        <span className="pointer-events-none absolute left-4 top-4 text-slate-500">
          <Conversation />
        </span>
        <textarea
          className="min-h-[3.5rem] w-full resize-none bg-transparent px-4 py-4 pl-11 pr-28 text-base text-white placeholder:text-slate-500 focus:outline-none"
          ref={textareaReference}
          value={message}
          placeholder="Still et oppfølgingsspørsmål"
          onKeyDown={handleKeyDown}
          onChange={handleChange}
          disabled={isMessageLoading}
        />
        {isMessageLoading ? (
          <button
            type="button"
            onClick={onAbortRequest}
            className="absolute bottom-2 right-2 inline-flex h-10 items-center gap-2 rounded-lg border border-rose-400/60 bg-rose-500/20 px-4 text-sm font-semibold text-rose-100 transition hover:bg-rose-500/30"
          >
            <StopIcon width={18} height={18} />
            Avbryt
          </button>
        ) : (
          <button
            disabled={isSubmitDisabled}
            type="submit"
            className="absolute bottom-2 right-2 inline-flex h-10 items-center gap-2 rounded-lg bg-gradient-to-r from-blue-500 to-blue-400 px-4 text-sm font-semibold text-white shadow-md shadow-blue-900/40 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
          >
            Send
            <SendIcon width={18} height={18} />
          </button>
        )}
      </div>
      <p className="text-xs text-slate-500">
        Trykk Enter for å sende, Shift + Enter for ny linje.
      </p>
    </form>
  )
}
