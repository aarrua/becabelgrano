import { apiClient } from './client'
import { AuthResponse, UserResponse } from '../types/telemetry'

export async function loginApi(username: string, password: string): Promise<AuthResponse> {
  return apiClient<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export async function getCurrentUserApi(): Promise<UserResponse> {
  return apiClient<UserResponse>('/api/me', {
    method: 'GET',
  })
}
