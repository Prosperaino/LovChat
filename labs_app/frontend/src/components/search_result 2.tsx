import React, { useEffect, useRef, useState } from 'react'
import { plainTextToHtml } from 'lib/utils'
import { SourceIcon } from './source_icon'
import { SourceType } from '../types'
import { ReactComponent as ArrowDown } from 'images/chevron_down_icon.svg'

interface SearchResultProps extends SourceType {
  toggleSource: (source: string) => void
}

const TITLE_HEIGHT = 59

export const SearchResult: React.FC<SearchResultProps> = ({
  name,
  icon,
  url,
  source_path,
  summary,
  updated_at,
  expanded = false,
  toggleSource,
}) => {
  const ref = useRef<HTMLDivElement>(null)
  const [blockHeight, setBlockHeight] = useState<string | number>(0)

  // Prevent expand when click is on link
  const onToggle = (event) => !event.target.href && toggleSource(name)

  useEffect(() => {
    const blockHeight = ref.current?.clientHeight

    if (blockHeight) {
      setBlockHeight(blockHeight)
    }
  }, [summary])

  const updatedAtDate = new Date(updated_at || '')
  const summaries = summary ?? []
  const linkTarget = url || source_path || ''
  const renderSummary = (text: string) => {
    if (!text) {
      return ''
    }
    const trimmed = text.trim()
    if (!trimmed) {
      return ''
    }

    const maxLength = 520
    let snippet = trimmed
    if (trimmed.length > maxLength) {
      snippet = trimmed.slice(0, maxLength)
      const lastSpace = snippet.lastIndexOf(' ')
      if (lastSpace > 360) {
        snippet = snippet.slice(0, lastSpace)
      }
      snippet = `${snippet.trim()} …`
    }
    return plainTextToHtml(snippet)
  }

  return (
    <div className="flex flex-col">
      <div
        onClick={onToggle}
        className="ease-in duration-300 overflow-hidden cursor-pointer bg-gray-50 rounded-md shadow-md hover:-translate-y-1 hover:shadow-lg"
        style={{ height: `${expanded ? blockHeight : TITLE_HEIGHT}px` }}
      >
        <div
          className="p-4 grid grid-cols-[auto_auto] gap-2 items-start overflow-hidden"
          data-source={name}
          ref={ref}
        >
          <SourceIcon
            className="bg-white rounded-md flex justify-center px-2 py-1 text-slate-400 text-xs"
            icon={icon}
          />
          <div className="inline-flex gap-4 justify-between overflow-hidden">
            <h4 className="flex flex-row space-x-1.5 pb-2 text-md mb-1 font-semibold overflow-ellipsis overflow-hidden whitespace-nowrap text-blue-500 text-lg">
              {name}
            </h4>
            <ArrowDown
              className={`ease-in duration-300 flex-shrink-0 ${
                expanded ? 'rotate-180' : 'rotate-0'
              }`}
            />
          </div>
          {linkTarget ? (
            <>
              <span className="bg-white rounded-md flex justify-center px-2 py-1 text-slate-400 text-xs">
                Lenke
              </span>
              <a
                className="hover:text-blue-800 text-blue-500 text-sm overflow-ellipsis overflow-hidden whitespace-nowrap"
                target="_blank"
                rel="noreferrer"
                href={linkTarget}
              >
                {linkTarget}
              </a>
            </>
          ) : (
            <>
              <span className="bg-white rounded-md flex justify-center px-2 py-1 text-slate-400 text-xs">
                Lenke
              </span>
              <span className="text-sm text-slate-500">Ikke tilgjengelig</span>
            </>
          )}
          {summaries.map((text, index) => (
            <React.Fragment key={index}>
              <span className="bg-white rounded-md flex justify-center px-2 py-1 text-slate-400 text-xs">
                Utdrag
              </span>
              <div
                className="text-sm leading-relaxed text-slate-700 bg-white border border-blue-100 rounded-md px-3 py-2 mb-3 shadow-inner [&>p]:mb-2 [&>p:last-child]:mb-0"
                dangerouslySetInnerHTML={{ __html: renderSummary(text) }}
              ></div>
            </React.Fragment>
          ))}
        </div>
      </div>
      {updated_at && (
        <span className="self-end mt-1 text-zinc-400 text-xs tracking-tight font-medium uppercase">
          {`UPDATED ${updatedAtDate.toLocaleDateString('common', {
            month: 'short',
          })} ${updatedAtDate.toLocaleDateString('common', {
            day: 'numeric',
          })}, ${updatedAtDate.getFullYear()}`}
        </span>
      )}
    </div>
  )
}
