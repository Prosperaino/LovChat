import React from 'react'

import { AppStatus } from 'store/provider'

type StatusTimelineProps = {
  status: AppStatus
  messages: string[]
  sessionId: string | null
}

const statusLabel: Record<AppStatus, { title: string; tone: string }> = {
  [AppStatus.Idle]: {
    title: 'Klar for neste spørsmål',
    tone: 'text-slate-300',
  },
  [AppStatus.StreamingMessage]: {
    title: 'Analyserer lovverket',
    tone: 'text-blue-200',
  },
  [AppStatus.Done]: {
    title: 'Svar klart',
    tone: 'text-emerald-200',
  },
  [AppStatus.Error]: {
    title: 'Noe gikk galt',
    tone: 'text-rose-200',
  },
}

const fallbackMessages: Record<AppStatus, string[]> = {
  [AppStatus.Idle]: [
    'Still et spørsmål for å starte et nytt søk i lovverket.',
  ],
  [AppStatus.StreamingMessage]: [
    'Starter søket mot Lovdata…',
    'Henter og vurderer relevante kilder…',
    'Setter sammen et strukturert svar.',
  ],
  [AppStatus.Done]: [
    'Et strukturert svar er klart, og kildene kan utforskes i detalj.',
  ],
  [AppStatus.Error]: [
    'Vi klarte ikke å fullføre forespørselen. Prøv igjen, eller endre spørsmålet litt.',
  ],
}

const currentTone = (status: AppStatus) => {
  switch (status) {
    case AppStatus.StreamingMessage:
      return 'bg-blue-400/80'
    case AppStatus.Done:
      return 'bg-emerald-400/80'
    case AppStatus.Error:
      return 'bg-rose-400/80'
    default:
      return 'bg-slate-500/60'
  }
}

export const StatusTimeline: React.FC<StatusTimelineProps> = ({
  status,
  messages,
  sessionId,
}) => {
  const displayMessages = messages.length
    ? messages
    : fallbackMessages[status] ?? fallbackMessages[AppStatus.Idle]
  const statusMeta = statusLabel[status] ?? statusLabel[AppStatus.Idle]

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-lg shadow-blue-950/30">
      <header className="flex flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
          STATUS
        </span>
        <h2 className={`text-lg font-semibold leading-tight ${statusMeta.tone}`}>
          {statusMeta.title}
        </h2>
        {sessionId && (
          <p className="text-xs font-mono text-slate-500">
            Sesjon:{' '}
            <span className="text-slate-300">
              {sessionId.slice(0, 8)}…{sessionId.slice(-4)}
            </span>
          </p>
        )}
      </header>

      <ol className="mt-5 flex flex-col gap-4">
        {displayMessages.map((message, index) => (
          <li
            key={`${message}-${index}`}
            className="group relative flex gap-3 pl-4 text-sm text-slate-300"
          >
            <span
              className={`absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full shadow-sm ${currentTone(
                index === displayMessages.length - 1
                  ? status
                  : AppStatus.StreamingMessage
              )}`}
            />
            <span className="flex-1 leading-relaxed">{message}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
