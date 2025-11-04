import React, { useMemo, useState } from 'react'

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
import { SearchResults } from './components/search_results'
import { StatusTimeline } from './components/status_timeline'

const SUGGESTED_QUERIES = [
  'Hva sier arbeidsmiljøloven om overtid?',
  'Hvordan definerer plan- og bygningsloven midlertidige bygg?',
  'Hvilke krav gjelder for personvern ved kameraovervåking?',
  'Hva er fristen for å klage på byggesøknad?',
  'Når kan midlertidige ansettelser avsluttes?',
]

const CONTROLLED_STATUS_REGEX = /^\[(SESSION_ID|SOURCE|CONTEXTS|CHUNK|DONE)\]/i
const JSON_LIKE_REGEX = /^[{\[]/

const normaliseStatusMessages = (
  messages: string[],
  sessionId: string | null
) => {
  const trimmedMessages = messages
    .map((message) => (message ?? '').trim())
    .filter((message) => message.length > 0)
    .filter((message) => !CONTROLLED_STATUS_REGEX.test(message))
    .filter((message) => !JSON_LIKE_REGEX.test(message))
    .map((message) =>
      message.replace(/^\[STATUS\]\s*/i, '').replace(sessionId || '', '').trim()
    )
    .filter((message) => message.length > 0)

  return trimmedMessages.filter(
    (message, index) => trimmedMessages.indexOf(message) === index
  )
}

const App = () => {
  const dispatch = useAppDispatch()
  const status = useAppSelector((state) => state.status)
  const sources = useAppSelector((state) => state.sources)
  const history = useAppSelector((state) => state.history)
  const sessionId = useAppSelector((state) => state.sessionId)
  const statusMessages = useAppSelector((state) => state.statusMessages)
  const conversation = useAppSelector((state) => state.conversation)
  const [summary, ...messages] = conversation
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

  const handleToggleSource = (name: string) => {
    dispatch(actions.sourceToggle({ name }))
  }

  const handleSourceClick = (name: string) => {
    dispatch(actions.sourceToggle({ name, expanded: true }))

    setTimeout(() => {
      document
        .querySelector(`[data-source=\"${name}\"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 200)
  }

  const handleSelectHistory = (query: string) => {
    setSearchQuery(query)
    handleSearch(query)
  }

  const showHero = status === AppStatus.Idle && !conversation.length
  const cleanedStatusMessages = useMemo(
    () => normaliseStatusMessages(statusMessages, sessionId),
    [statusMessages, sessionId]
  )
  const hasConversationStarted = conversation.length > 0

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <Header sessionId={sessionId} />

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 pb-16 pt-10 md:px-8">
        <section className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.04] p-6 backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-white md:text-3xl">
                Still et spørsmål om norsk lovgivning
              </h1>
              <p className="mt-1 text-sm text-slate-300 md:text-base">
                GPTLov finner relevante kilder fra Lovdata og gir deg et
                begrunnet svar med kildehenvisninger.
              </p>
            </div>
            <div className="w-full max-w-xl">
              <SearchInput
                onSearch={handleSearch}
                value={searchQuery}
                appStatus={status}
              />
            </div>
          </div>

          {!!history.length && (
            <div className="flex flex-col gap-3">
              <h2 className="text-sm font-medium uppercase tracking-wide text-slate-400">
                Tidligere spørsmål
              </h2>
              <div className="flex flex-wrap gap-2">
                {history.map((item) => (
                  <button
                    key={item}
                    className="group flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-slate-200 transition hover:-translate-y-0.5 hover:border-blue-400/60 hover:bg-blue-500/20 hover:text-white"
                    onClick={(event) => {
                      event.preventDefault()
                      handleSelectHistory(item)
                    }}
                  >
                    <span className="inline-block h-2 w-2 rounded-full bg-blue-400/80" />
                    {item}
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {showHero && (
          <Hero
            suggestedQueries={SUGGESTED_QUERIES}
            onSelect={(query) => {
              setSearchQuery(query)
              handleSearch(query)
            }}
          />
        )}

        <section className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-6">
            {hasConversationStarted ? (
              <Chat
                status={status}
                messages={messages}
                summary={summary}
                onSend={handleSendChatMessage}
                onAbortRequest={handleAbortRequest}
                onSourceClick={handleSourceClick}
              />
            ) : (
              !showHero && (
                <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-12 text-center text-slate-300">
                  <div
                    className="h-12 w-12 animate-spin rounded-full border-2 border-blue-400/40 border-t-blue-400"
                    aria-hidden="true"
                  />
                  <div className="space-y-2">
                    <p className="text-base font-medium text-slate-200">
                      Leter i lovverket etter svar …
                    </p>
                    {cleanedStatusMessages.length ? (
                      cleanedStatusMessages.map((message) => (
                        <p key={message} className="text-sm text-slate-400">
                          {message}
                        </p>
                      ))
                    ) : (
                      <p className="text-sm text-slate-400">
                        Følger spor av relevante paragrafer og forarbeider.
                      </p>
                    )}
                  </div>
                </div>
              )
            )}
          </div>

          <aside className="flex flex-col gap-6">
            <StatusTimeline
              status={status}
              messages={cleanedStatusMessages}
              sessionId={sessionId}
            />

            <SearchResults
              results={sources}
              toggleSource={handleToggleSource}
            />
          </aside>
        </section>
      </main>
    </div>
  )
}

type HeroProps = {
  suggestedQueries: string[]
  onSelect: (query: string) => void
}

const Hero: React.FC<HeroProps> = ({ suggestedQueries, onSelect }) => (
  <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.06] via-white/[0.03] to-transparent p-8 shadow-lg shadow-blue-950/40">
    <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-white md:text-2xl">
          Kom i gang med et eksempel
        </h2>
        <p className="mt-2 max-w-xl text-sm text-slate-300 md:text-base">
          Ikke sikker på hva du skal spørre om? Prøv et av forslagene under og
          utforsk hvordan GPTLov henter frem relevante lovhenvisninger.
        </p>
      </div>
    </div>
    <div className="mt-6 grid gap-4 md:grid-cols-2">
      {suggestedQueries.map((query) => (
        <button
          key={query}
          className="group flex h-full flex-col justify-between gap-4 rounded-xl border border-white/10 bg-white/[0.04] p-5 text-left text-slate-200 transition hover:-translate-y-1 hover:border-blue-400/60 hover:bg-blue-500/15 hover:text-white"
          onClick={(event) => {
            event.preventDefault()
            onSelect(query)
          }}
        >
          <span className="text-base font-medium leading-relaxed">
            {query}
          </span>
          <span className="inline-flex items-center gap-2 text-sm font-medium text-blue-300 transition group-hover:text-white">
            Utforsk foreslått spørsmål
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M3 10a1 1 0 011-1h8.586L9.293 5.707a1 1 0 011.414-1.414l5.5 5.5a1 1 0 010 1.414l-5.5 5.5a1 1 0 11-1.414-1.414L12.586 11H4a1 1 0 01-1-1z"
                clipRule="evenodd"
              />
            </svg>
          </span>
        </button>
      ))}
    </div>
  </section>
)

export default App
