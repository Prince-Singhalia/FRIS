import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearSession, getDashboard, getUser, login } from './api'

function jsonResponse(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  }
}

describe('API client', () => {
  afterEach(() => {
    clearSession()
    vi.unstubAllGlobals()
  })

  it('sends OAuth form credentials and attaches the access token to authenticated requests', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'access-value', refresh_token: 'refresh-value', token_type: 'bearer' }))
      .mockResolvedValueOnce(jsonResponse({ id: 'user-id' }))
    vi.stubGlobal('fetch', fetchMock)

    await login('north-campus/admin', 'example-password')
    await getUser()

    const [loginUrl, loginInit] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(loginUrl).toBe('/api/v1/auth/login')
    expect(loginInit.body).toBeInstanceOf(URLSearchParams)
    expect((loginInit.body as URLSearchParams).get('username')).toBe('north-campus/admin')
    const [, userInit] = fetchMock.mock.calls[1] as [string, RequestInit]
    expect(new Headers(userInit.headers).get('Authorization')).toBe('Bearer access-value')
  })

  it('surfaces API errors and clears an expired session', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ access_token: 'access-value', refresh_token: 'refresh-value', token_type: 'bearer' }))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Token expired' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Refresh rejected' }, 401))
    vi.stubGlobal('fetch', fetchMock)

    await login('north-campus/admin', 'example-password')
    await expect(getDashboard()).rejects.toMatchObject({
      name: 'ApiError',
      message: 'Token expired',
      status: 401,
    })
  })
})
