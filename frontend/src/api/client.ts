import { ApiError } from '../types/telemetry'

const TOKEN_KEY = 'tanques_jwt'

let inMemoryToken: string | null = null

export function getStoredToken(): string | null {
  if (inMemoryToken) return inMemoryToken
  try {
    const saved = sessionStorage.getItem(TOKEN_KEY)
    if (saved) {
      inMemoryToken = saved
      return saved
    }
  } catch {
    // sessionStorage inaccesible o bloqueado
  }
  return null
}

export function setStoredToken(token: string | null): void {
  inMemoryToken = token
  try {
    if (token) {
      sessionStorage.setItem(TOKEN_KEY, token)
    } else {
      sessionStorage.removeItem(TOKEN_KEY)
    }
  } catch {
    // sessionStorage inaccesible o bloqueado
  }
}

let onUnauthorizedCallback: (() => void) | null = null

export function setOnUnauthorizedCallback(cb: (() => void) | null) {
  onUnauthorizedCallback = cb
}

export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken()

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  })

  if (response.status === 401) {
    setStoredToken(null)
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback()
    }
    const err: ApiError = {
      status: 401,
      message: 'Sesión expirada o credenciales inválidas',
    }
    throw err
  }

  if (!response.ok) {
    let errorData: any = null
    try {
      errorData = await response.json()
    } catch {
      // no es JSON
    }

    const err: ApiError = {
      status: response.status,
      message: errorData?.message || response.statusText || 'Error en la solicitud',
      reason: errorData?.reason,
    }
    throw err
  }

  if (response.status === 204) {
    return {} as T
  }

  return response.json()
}
