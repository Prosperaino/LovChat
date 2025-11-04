import type { TypedUseSelectorHook } from 'react-redux'
import { Provider, useDispatch, useSelector } from 'react-redux'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { configureStore, createSlice } from '@reduxjs/toolkit'
import { SourceType, ChatMessageType } from 'types'

const HISTORY_STORAGE_KEY = 'gptlov_history'
const MAX_HISTORY_ENTRIES = 20

const loadHistory = (): string[] => {
  if (typeof window === 'undefined') {
    return []
  }

  try {
    const raw = window.localStorage.getItem(HISTORY_STORAGE_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.filter((item) => typeof item === 'string').slice(0, MAX_HISTORY_ENTRIES)
  } catch (error) {
    console.warn('Kunne ikke lese historikk fra localStorage.', error)
    return []
  }
}

const persistHistory = (history: string[]) => {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(
      HISTORY_STORAGE_KEY,
      JSON.stringify(history.slice(0, MAX_HISTORY_ENTRIES))
    )
  } catch (error) {
    console.warn('Kunne ikke lagre historikk til localStorage.', error)
  }
}

const normaliseQuestion = (value: string) => value.trim()

const buildHistoryList = (history: string[], question: string): string[] => {
  const normalized = normaliseQuestion(question)
  if (!normalized.length) {
    return history
  }

  const existing = history.filter(
    (entry) => entry.localeCompare(normalized, undefined, { sensitivity: 'accent' }) !== 0
  )
  return [normalized, ...existing].slice(0, MAX_HISTORY_ENTRIES)
}

type GlobalStateType = {
  status: AppStatus
  conversation: ChatMessageType[]
  sources: SourceType[]
  sessionId: string | null
  history: string[]
  statusMessages: string[]
}

class RetriableError extends Error {}
class FatalError extends Error {}
export enum AppStatus {
  Idle = 'idle',
  StreamingMessage = 'loading',
  Done = 'done',
  Error = 'error',
}
enum STREAMING_EVENTS {
  SESSION_ID = 'session_id',
  SOURCE = 'source',
  ANSWER_HTML = 'answer_html',
  STATUS = 'status',
  SOURCE_LIST = 'source_list',
  CHUNK = 'chunk',
  CONTEXTS = 'contexts',
  DONE = 'done',
}

const GLOBAL_STATE: GlobalStateType = {
  status: AppStatus.Idle,
  conversation: [],
  sessionId: null,
  sources: [],
  history: loadHistory(),
  statusMessages: [],
}

const resolveApiHost = () => {
  const envHost = process.env.REACT_APP_API_HOST?.trim()
  if (envHost && envHost.length) {
    return envHost.replace(/\/$/, '')
  }

  if (typeof window !== 'undefined' && window.location?.origin) {
    return `${window.location.origin.replace(/\/$/, '')}/api`
  }

  return '/api'
}

const API_HOST = resolveApiHost()

let abortController: AbortController | null = null
const globalSlice = createSlice({
  name: 'global',
  initialState: GLOBAL_STATE as GlobalStateType,
  reducers: {
    addSource: (state, action) => {
      const source = action.payload.source
      const rootSource = state.sources.find((s) => s.name === source.name)

      if (rootSource) {
        if (!rootSource.summary.find((summary) => summary === source.summary)) {
          rootSource.summary = [...rootSource.summary, source.summary]
        }
      } else {
        state.sources.push({
          ...source,
          summary: [source.summary],
          expanded: false,
        })
      }
    },
    setStatus: (state, action) => {
      state.status = action.payload.status
    },
    setSessionId: (state, action) => {
      state.sessionId = action.payload.sessionId
    },
    addMessage: (state, action) => {
      state.conversation.push(action.payload.conversation)
    },
    updateMessage: (state, action) => {
      const messageIndex = state.conversation.findIndex(
        (c) => c.id === action.payload.id
      )

      if (messageIndex !== -1) {
        state.conversation[messageIndex] = {
          ...state.conversation[messageIndex],
          ...action.payload,
        }
      }
    },
    setMessageSource: (state, action) => {
      const message = state.conversation.find((c) => c.id === action.payload.id)

      if (message) {
        message.sources = action.payload.sources
          .map((sourceName) =>
            state.sources.find((stateSource) => stateSource.name === sourceName)
          )
          .filter((source) => !!source)
      }
    },
    removeMessage: (state, action) => {
      const messageIndex = state.conversation.findIndex(
        (c) => c.id === action.payload.id
      )

      if (messageIndex !== -1) {
        state.conversation.splice(messageIndex, 1)
      }
    },
    sourceToggle: (state, action) => {
      const source = state.sources.find((s) => s.name === action.payload.name)

      if (source) {
        source.expanded = action.payload.expanded ?? !source.expanded
      }
    },
    setHistory: (state, action) => {
      state.history = action.payload.history
    },
    addStatusMessage: (state, action) => {
      state.statusMessages = [...state.statusMessages, action.payload.message]
    },
    resetStatusMessages: (state) => {
      state.statusMessages = []
    },
    reset: (state) => {
      state.status = AppStatus.Idle
      state.sessionId = null
      state.conversation = []
      state.sources = []
      state.statusMessages = []
    },
  },
})

const store = configureStore({
  reducer: globalSlice.reducer,
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
export const useAppDispatch: () => AppDispatch = useDispatch
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector
export const actions = globalSlice.actions

export const thunkActions = {
  search: (query: string) => {
    return async function fetchSearch(dispatch, getState) {
      if (getState().status === AppStatus.StreamingMessage) {
        dispatch(thunkActions.abortRequest())
      }

      dispatch(thunkActions.recordHistory(query))
      dispatch(actions.reset())
      dispatch(thunkActions.chat(query))
    }
  },
  askQuestion: (question: string) => {
    return async function (dispatch, getState) {
      const state = getState()

      dispatch(thunkActions.recordHistory(question))
      dispatch(
        actions.addMessage({
          conversation: {
            isHuman: true,
            content: question,
            id: state.conversation.length + 1,
          },
        })
      )
      dispatch(thunkActions.chat(question))
    }
  },
  recordHistory: (question: string) => {
    return function (dispatch, getState) {
      const state = getState()
      const nextHistory = buildHistoryList(state.history, question)
      const historyChanged =
        nextHistory.length !== state.history.length ||
        nextHistory.some((entry, index) => state.history[index] !== entry)

      if (historyChanged) {
        dispatch(
          actions.setHistory({
            history: nextHistory,
          })
        )
        persistHistory(nextHistory)
      }
    }
  },
  chat: (question: string) => {
    return async function fetchSearch(dispatch, getState) {
      abortController = new AbortController()
      const conversationId = getState().conversation.length + 1

      dispatch(
        actions.addMessage({
          conversation: {
            isHuman: false,
            content: '',
            id: conversationId,
          },
        })
      )
      dispatch(actions.resetStatusMessages())
      dispatch(
        actions.addStatusMessage({
          message: 'Starter søk i lovverket…',
        })
      )
      dispatch(actions.setStatus({ status: AppStatus.StreamingMessage }))

      let countRetiresError = 0
      let message = ''
      const sessionId = getState().sessionId

      await fetchEventSource(
        `${API_HOST}/chat${sessionId ? `?session_id=${sessionId}` : ''}`,
        {
          method: 'POST',
          openWhenHidden: true,
          body: JSON.stringify({
            question,
          }),
          headers: {
            'Content-Type': 'application/json',
          },
          signal: abortController.signal,
          async onmessage(event) {
            const rawEventData =
              typeof event.data === 'string' ? event.data.trim() : ''
            let payloadType = event.event || ''
            let payloadData: unknown = event.data

            if (rawEventData.length) {
              if (payloadType === FatalError.name) {
                // fatal errors arrive as plain text in some environments
                throw new FatalError(rawEventData)
              }

              try {
                payloadData = JSON.parse(rawEventData)
              } catch {
                payloadData = rawEventData
              }
            }

            if (!payloadType) {
              if (typeof payloadData === 'string') {
                const legacyMatch = payloadData.match(/^\[([A-Z_]+)\]\s*([\s\S]*)$/)
                if (legacyMatch) {
                  payloadType = legacyMatch[1].toLowerCase()
                  const legacyPayload = legacyMatch[2].trim()

                  if (legacyPayload.startsWith('{') || legacyPayload.startsWith('[')) {
                    try {
                      payloadData = JSON.parse(legacyPayload)
                    } catch {
                      payloadData = legacyPayload
                    }
                  } else if (legacyPayload.length) {
                    payloadData = legacyPayload
                  } else {
                    payloadData = null
                  }
                } else if (payloadData.length) {
                  payloadType = STREAMING_EVENTS.CHUNK
                }
              } else if (rawEventData.length) {
                payloadType = STREAMING_EVENTS.CHUNK
                payloadData = rawEventData
              }
            }

            if (payloadType === 'fatalerror') {
              throw new FatalError(event.data)
            }

            if (payloadType === STREAMING_EVENTS.SESSION_ID) {
              const sessionId = typeof payloadData === 'string' ? payloadData.trim() : ''
              dispatch(actions.setSessionId({ sessionId }))
            } else if (payloadType === STREAMING_EVENTS.SOURCE) {
              const source = payloadData as {
                name?: string
                page_content?: string
                url?: string
                source_path?: string
                category?: string
                updated_at?: string | null
              }

              if (source?.page_content && source?.name) {
                const link = source.url || source.source_path || ''
                dispatch(
                  actions.addSource({
                    source: {
                      name: source.name,
                      url: link || undefined,
                      source_path: source.source_path,
                      summary: source.page_content,
                      icon: source.category,
                      updated_at: source.updated_at,
                    },
                  })
                )
              }
            } else if (payloadType === STREAMING_EVENTS.STATUS) {
              let statusMessage = ''
              if (typeof payloadData === 'string') {
                statusMessage = payloadData.trim()
              } else if (
                payloadData &&
                typeof payloadData === 'object' &&
                'message' in (payloadData as Record<string, unknown>)
              ) {
                const candidate = (payloadData as Record<string, unknown>).message
                if (typeof candidate === 'string') {
                  statusMessage = candidate.trim()
                }
              }

              if (statusMessage) {
                dispatch(
                  actions.addStatusMessage({
                    message: statusMessage,
                  })
                )
              }
            } else if (payloadType === STREAMING_EVENTS.SOURCE_LIST) {
              const names = Array.isArray((payloadData as any)?.names)
                ? (payloadData as any).names
                : Array.isArray(payloadData)
                  ? (payloadData as any[])
                  : []

              if (names.length) {
                dispatch(
                  actions.setMessageSource({
                    id: conversationId,
                    sources: names,
                  })
                )
                dispatch(
                  actions.addStatusMessage({
                    message: `Fant ${names.length} relevante utdrag – analyserer…`,
                  })
                )
              }
            } else if (payloadType === STREAMING_EVENTS.CONTEXTS) {
              // Context metadata already handled via SOURCE events
            } else if (payloadType === STREAMING_EVENTS.ANSWER_HTML) {
              if (typeof payloadData === 'string') {
                dispatch(
                  actions.updateMessage({
                    id: conversationId,
                    contentHtml: payloadData,
                  })
                )
              }
            } else if (payloadType === STREAMING_EVENTS.CHUNK) {
              const chunk = typeof payloadData === 'string' ? payloadData : ''
              if (chunk) {
                message += chunk

                dispatch(
                  actions.updateMessage({
                    id: conversationId,
                    content: message,
                  })
                )
              }
            } else if (payloadType === STREAMING_EVENTS.DONE) {
              dispatch(actions.addStatusMessage({ message: 'Ferdig.' }))
              dispatch(actions.setStatus({ status: AppStatus.Done }))
            } else if (payloadData) {
              // Fallback for unexpected events: treat payload as status snippet
              dispatch(
                actions.addStatusMessage({
                  message: String(payloadData).trim(),
                })
              )
            }
          },
          async onopen(response) {

            if (response.ok) {
              return
            } else if (
              response.status >= 400 &&
              response.status < 500 &&
              response.status !== 429
            ) {
              throw new FatalError()
            } else {
              throw new RetriableError()
            }
          },
          onerror(err) {
            if (err instanceof FatalError || countRetiresError > 3) {
              const message =
                err instanceof FatalError && typeof err.message === 'string' && err.message.trim()
                  ? err.message.trim()
                  : 'Klarte ikke å hente svar fra GPTLov. Kontroller tilkoblingen og prøv igjen.'

              dispatch(
                actions.addStatusMessage({
                  message,
                })
              )
              dispatch(actions.setStatus({ status: AppStatus.Error }))

              throw err
            } else {
              countRetiresError++
              console.error(err)
            }
          },
        }
      )
    }
  },
  abortRequest: () => {
    return function (dispatch, getState) {
      const messages = getState().conversation
      const lastMessage = messages[messages.length - 1]

      abortController?.abort()
      abortController = null

      if (lastMessage && !lastMessage.content) {
        dispatch(
          actions.removeMessage({
            id: lastMessage.id,
          })
        )
      }
      dispatch(
        actions.setStatus({
          status: messages.length ? AppStatus.Done : AppStatus.Idle,
        })
      )
      dispatch(actions.resetStatusMessages())
    }
  },
}

export const GlobalStateProvider = ({ children }) => {
  return <Provider store={store}>{children}</Provider>
}
