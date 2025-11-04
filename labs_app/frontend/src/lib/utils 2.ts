import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function escapeHtml(value: string): string {
  if (!value) {
    return ''
  }
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function plainTextToHtml(text: string): string {
  if (!text) {
    return ''
  }

  const normalized = text.replace(/\r\n?/g, '\n').trim()
  if (!normalized) {
    return ''
  }

  const splitIntoParagraphs = (value: string) => {
    const explicitParagraphs = value.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean)
    if (explicitParagraphs.length > 1) {
      return explicitParagraphs
    }

    const sentences = value
      .split(/(?<=[.!?])\s+(?=[A-ZÆØÅÄÖÜÉÈ0-9«(])/)
      .map((sentence) => sentence.trim())
      .filter(Boolean)

    if (sentences.length <= 1) {
      return [value.trim()]
    }

    const paragraphs: string[] = []
    let buffer: string[] = []
    let bufferLength = 0

    sentences.forEach((sentence) => {
      buffer.push(sentence)
      bufferLength += sentence.length
      const shouldFlush = bufferLength >= 220 || sentence.endsWith(':') || buffer.length >= 2

      if (shouldFlush) {
        paragraphs.push(buffer.join(' ').trim())
        buffer = []
        bufferLength = 0
      }
    })

    if (buffer.length) {
      paragraphs.push(buffer.join(' ').trim())
    }

    return paragraphs
  }

  const renderListFromParagraph = (paragraph: string) => {
    const colonIndex = paragraph.indexOf(':')
    if (colonIndex === -1) {
      return ''
    }

    const lead = paragraph.slice(0, colonIndex).trim()
    const remainder = paragraph.slice(colonIndex + 1).trim()
    const listItems = remainder.split(/;\s+/).map((item) => item.trim()).filter(Boolean)

    if (listItems.length < 2) {
      return ''
    }

    const heading = escapeHtml(lead.endsWith(':') ? lead.slice(0, -1) : lead)
    const itemsHtml = listItems.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
    return `<p><strong>${heading}:</strong></p><ul>${itemsHtml}</ul>`
  }

  return splitIntoParagraphs(normalized)
    .map((paragraph) => {
      const listHtml = renderListFromParagraph(paragraph)
      if (listHtml) {
        return listHtml
      }

      const escaped = escapeHtml(paragraph)
      return `<p>${escaped.replace(/\n+/g, '<br />')}</p>`
    })
    .join('')
}
