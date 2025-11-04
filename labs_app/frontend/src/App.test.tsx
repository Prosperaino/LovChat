import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import App from './App'

jest.mock('./store/provider', () => {
  const actual = jest.requireActual('./store/provider')

  return {
    ...actual,
    GlobalStateProvider: ({ children }: { children: React.ReactNode }) => (
      <>{children}</>
    ),
    useAppDispatch: () => jest.fn(),
    useAppSelector: (selector: (state: any) => any) =>
      selector({
        status: actual.AppStatus.Idle,
        sources: [],
        history: [],
        sessionId: null,
        statusMessages: [],
        conversation: [],
      }),
  }
})

test('renders hero prompt', () => {
  render(<App />)
  expect(
    screen.getByText(/Still et spørsmål om norsk lovgivning/i)
  ).toBeInTheDocument()
})
