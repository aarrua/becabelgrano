import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { UserResponse, UserRole } from '../types/telemetry'
import { loginApi, getCurrentUserApi } from '../api/auth'
import { getStoredToken, setStoredToken, setOnUnauthorizedCallback } from '../api/client'

interface AuthContextType {
  user: UserResponse | null
  token: string | null
  role: UserRole | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredToken())
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const logout = useCallback(() => {
    setStoredToken(null)
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setOnUnauthorizedCallback(logout)
    return () => setOnUnauthorizedCallback(null)
  }, [logout])

  useEffect(() => {
    async function initAuth() {
      const currentToken = getStoredToken()
      if (!currentToken) {
        setIsLoading(false)
        return
      }

      try {
        const profile = await getCurrentUserApi()
        setUser(profile)
        setToken(currentToken)
      } catch {
        logout()
      } finally {
        setIsLoading(false)
      }
    }

    initAuth()
  }, [logout])

  const login = async (username: string, password: string) => {
    const res = await loginApi(username, password)
    setStoredToken(res.token)
    setToken(res.token)
    setUser({ username: res.username, role: res.role })
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        role: user?.role ?? null,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
