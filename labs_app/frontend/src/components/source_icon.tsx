import React from 'react'

import confluence from 'images/confluence.png'
import docs from 'images/docs.png'
import dropbox from 'images/dropbox.png'
import excel from 'images/excel.png'
import onedrive from 'images/onedrive.png'
import pdf from 'images/pdf.png'
import github from 'images/github.png'
import sharepoint from 'images/sharepoint.png'
import sheets from 'images/sheets.png'
import slides from 'images/slides.png'
import teams from 'images/teams.png'
import sql_server from 'images/sql server.png'
import word from 'images/word.png'
import faq from 'images/faq.png'

const iconNameToImageMap = {
  confluence,
  docs,
  dropbox,
  excel,
  onedrive,
  pdf,
  sharepoint,
  sheets,
  slides,
  teams,
  sql_server,
  word,
  github,
  faq,
} as const

export type SourceIconType = {
  className?: string
  icon?: keyof typeof iconNameToImageMap | string | null | undefined
}
export const SourceIcon: React.FC<SourceIconType> = ({ className, icon }) => {
  const imageSrc =
    icon && iconNameToImageMap[icon as keyof typeof iconNameToImageMap]

  if (!imageSrc) {
    return (
      <span className={`${className} text-slate-500 font-medium`}>
        §
      </span>
    )
  }

  return (
    <span className={className}>
      <img className="w-6 h-6" src={imageSrc} alt={`${icon}`} />
    </span>
  )
}
