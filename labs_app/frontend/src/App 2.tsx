import React, { useState } from 'react'

import {
  actions,
  AppStatus,
  thunkActions,
  useAppDispatch,
  useAppSelector,
} from 'store/provider'
import { Header } from 'components/header'
import { Chat } from 'components/chat/chat'
import SearchInput from 'components/search_input'
import { ReactComponent as ChatIcon } from 'images/chat_icon.svg'
import { SearchResults } from './components/search_results'

const App = () => {
  const dispatch = useAppDispatch()
  const status = useAppSelector((state) => state.status)
  const sources = useAppSelector((state) => state.sources)
  const history = useAppSelector((state) => state.history)
  const [summary, ...messages] = useAppSelector((state) => state.conversation)
  const statusMessages = useAppSelector((state) => state.statusMessages)
  const hasSummary = useAppSelector(
    (state) => !!state.conversation?.[0]?.content
  )
  const [searchQuery, setSearchQuery] = useState<string>('')

  const handleSearch = (query: string) => {
    dispatch(thunkActions.search(query))
  }
  const handleSendChatMessage = (query: string) => {
    dispatch(thunkActions.askQuestion(query))
  }
  const handleAbortRequest = () => {
    dispatch(thunkActions.abortRequest())
  }
  const handleToggleSource = (name) => {
    dispatch(actions.sourceToggle({ name }))
  }
  const handleSourceClick = (name) => {
    dispatch(actions.sourceToggle({ name, expanded: true }))

    setTimeout(() => {
      document
        .querySelector(`[data-source="${name}"]`)
        ?.scrollIntoView({ behavior: 'smooth' })
    }, 300)
  }
  const handleSelectHistory = (query: string) => {
    setSearchQuery(query)
    handleSearch(query)
  }

  const suggestedQueries = [
    'Hva sier arbeidsmiljøloven om overtid?',
    'Hvordan definerer plan- og bygningsloven midlertidige bygg?',
    'Hvilke krav gjelder for personvern ved kameraovervåking?',
    'Hva er fristen for å klage på byggesøknad?',
    'Når kan midlertidige ansettelser avsluttes?',
  ]

  return (
    <>
      <Header />

      <div className="p-4 max-w-2xl mx-auto">
        <SearchInput
          onSearch={handleSearch}
          value={searchQuery}
          appStatus={status}
        />
        {!!history.length && (
          <div className="mt-4 mb-6">
            <h2 className="text-zinc-400 text-sm font-medium mb-2 inline-flex items-center gap-2">
              Tidligere spørsmål
            </h2>
            <div className="flex flex-wrap gap-2">
              {history.map((item) => (
                <button
                  key={item}
                  className="hover:-translate-y-0.5 hover:shadow hover:bg-white/80 border border-blue-200 text-blue-600 bg-white rounded-full px-3 py-1.5 text-sm transition"
                  onClick={(event) => {
                    event.preventDefault()
                    handleSelectHistory(item)
                  }}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        )}

        {status === AppStatus.Idle ? (
          <div className="mx-auto my-6">
            <h2 className="text-zinc-400 text-sm font-medium mb-3  inline-flex items-center gap-2">
              <ChatIcon /> Common questions
            </h2>
            <div className="flex flex-col space-y-4">
              {suggestedQueries.map((query) => (
                <button
                  key={query}
                  className="hover:-translate-y-1 hover:shadow-lg hover:bg-zinc-300 transition-transform h-12 px-4 py-2 bg-zinc-200 rounded-md shadow flex items-center text-zinc-700"
                  onClick={(e) => {
                    e.preventDefault()
                    setSearchQuery(query)
                    handleSearch(query)
                  }}
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {hasSummary ? (
              <div className="max-w-2xl mx-auto relative">
                <Chat
                  status={status}
                  messages={messages}
                  summary={summary}
                  onSend={handleSendChatMessage}
                  onAbortRequest={handleAbortRequest}
                  onSourceClick={handleSourceClick}
                />

                <SearchResults
                  results={sources}
                  toggleSource={handleToggleSource}
                />
              </div>
            ) : (
              <div className="h-36 p-6 bg-white rounded-md shadow flex flex-col justify-start items-center gap-4 mt-6">
                <div
                  className="h-10 w-10 rounded-full border-2 border-blue-200 border-t-blue-600 animate-spin"
                  aria-hidden="true"
                />
                <div className="flex flex-col gap-1 text-center text-zinc-500 text-sm">
                  {statusMessages.length ? (
                    statusMessages.map((message, index) => (
                      <p
                        key={`${message}-${index}`}
                        className={
                          index === statusMessages.length - 1
                            ? 'text-zinc-600 font-medium'
                            : undefined
                        }
                      >
                        {message}
                      </p>
                    ))
                  ) : (
                    <p>Leter i lovverket etter svar …</p>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}

export default App
