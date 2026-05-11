/// <reference types="vitest/globals" />
import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'
import { server } from './mocks/server'

// Mock styled-jsx (Next.js CSS-in-JS) for test environment
vi.mock('styled-jsx', () => ({
  style: ({ children }: { children: React.ReactNode }) => children,
}))

// Establish API mocking before all tests
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))

// Reset any request handlers that are declared during the tests
afterEach(() => server.resetHandlers())

// Clean up after the tests are finished
afterAll(() => server.close())
