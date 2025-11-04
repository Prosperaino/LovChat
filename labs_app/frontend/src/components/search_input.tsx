import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { ReactComponent as RefreshIcon } from 'images/refresh_icon.svg'
import { ReactComponent as SearchIcon } from 'images/search_icon.svg'
import { ReactComponent as ArrowIcon } from 'images/arrow_icon.svg'
import { AppStatus } from 'store/provider'

type SearchInputProps = {
  onSearch: (query: string) => void
  value: string
  appStatus: AppStatus
}

export default function SearchInput({
  onSearch,
  value,
  appStatus,
}: SearchInputProps) {
  const [query, setQuery] = useState<string>(value)

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    if (!!query.trim().length) {
      onSearch(query.trim())
    }
  }

  const handleChange = (event: ChangeEvent<HTMLInputElement>) =>
    setQuery(event.target.value)

  useEffect(() => {
    setQuery(value)
  }, [value])

  const isIdle = appStatus === AppStatus.Idle
  const isDisabled = !query.trim().length && isIdle

  return (
    <form className="w-full" onSubmit={handleSubmit}>
      <div className="relative flex w-full items-center overflow-hidden rounded-xl border border-white/10 bg-slate-900/70 shadow-inner shadow-black/40 backdrop-blur transition focus-within:border-blue-400/60 focus-within:shadow-blue-500/20">
        <span className="pointer-events-none pl-4 text-slate-500">
          <SearchIcon width={20} height={20} />
        </span>
        <input
          type="search"
          className="h-14 w-full bg-transparent px-4 text-base font-medium text-white placeholder:text-slate-500 focus:outline-none"
          value={query}
          onChange={handleChange}
          placeholder="Still et spørsmål om norsk lov"
        />
        {isIdle ? (
          <button
            className="mr-2 inline-flex h-11 items-center gap-2 rounded-lg bg-gradient-to-r from-blue-500 to-blue-400 px-4 text-sm font-semibold text-white shadow-lg shadow-blue-900/40 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
            type="submit"
            disabled={isDisabled}
          >
            Send
            <ArrowIcon width={18} height={18} />
          </button>
        ) : (
          <button
            className="mr-2 inline-flex h-11 items-center gap-2 rounded-lg border border-blue-300/60 bg-blue-500/10 px-4 text-sm font-semibold text-blue-200 transition hover:bg-blue-500/20"
            type="submit"
          >
            <RefreshIcon width={18} height={18} />
            Nullstill
          </button>
        )}
      </div>
    </form>
  )
}
