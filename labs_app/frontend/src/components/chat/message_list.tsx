import React, { useEffect, useRef, useState } from 'react'
import { ChatMessage } from './message'
import { ChatMessageType } from 'types'

type ChatMessageListType = {
  messages: ChatMessageType[]
  isMessageLoading: boolean
  onSourceClick: (source: string) => void
}
export const ChatMessageList: React.FC<ChatMessageListType> = ({
  messages,
  isMessageLoading,
  onSourceClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [userScrolled, setUserScrolled] = useState(false)

  useEffect(() => {
    const container = containerRef.current
    // Scroll to bottom when new messages come in and the user hasn't scrolled up
    if (container && !userScrolled) {
      container.scrollTop = container.scrollHeight
    }
  }, [messages, userScrolled])

  const handleScroll = () => {
    const container = containerRef.current
    // Check if the user has scrolled up
    if (container) {
      const { scrollTop, clientHeight, scrollHeight } = container
      const isAtBottom = scrollTop + clientHeight >= scrollHeight
      setUserScrolled(!isAtBottom)
    }
  }

  return (
    <div
      className="max-h-[26rem] space-y-6 overflow-y-auto pr-1"
      ref={containerRef}
      onScroll={handleScroll}
    >
      {messages.map((message, index) => (
        <ChatMessage
          key={message.id}
          loading={
            messages.length - 1 === index &&
            !message.content.length &&
            isMessageLoading
          }
          onSourceClick={onSourceClick}
          {...message}
        />
      ))}
    </div>
  )
}
