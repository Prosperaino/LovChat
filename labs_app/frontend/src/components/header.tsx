type HeaderProps = {
  sessionId?: string | null
}

export const Header: React.FC<HeaderProps> = ({ sessionId }) => (
  <header className="w-full border-b border-white/10 bg-slate-950/90 pb-4 pt-6 text-white backdrop-blur">
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 md:flex-row md:items-center md:justify-between md:px-8">
      <div className="flex items-center gap-3">
        <a
          href="/"
          className="text-2xl font-semibold tracking-tight text-white transition hover:text-blue-200"
        >
          Prosper AI Labs - GPTLov 
        </a>
        <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-widest text-slate-200">
          Eksperiment
        </span>
      </div>

      <div className="flex flex-col items-start gap-1 text-sm text-slate-300 md:items-end">
        <span>Utforsk Lovdata med en kildebevisst assistent.</span>
        {sessionId && (
          <span className="font-mono text-xs text-slate-500">
            Aktiv sesjon: {sessionId.slice(0, 8)}…{sessionId.slice(-4)}
          </span>
        )}
      </div>
    </div>
  </header>
)
