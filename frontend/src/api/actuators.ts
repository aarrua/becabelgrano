import { apiClient } from './client'
import { ActuatorCommandResponse } from '../types/telemetry'

export async function fetchActuators(): Promise<Record<string, boolean>> {
  return apiClient<Record<string, boolean>>('/api/actuators', {
    method: 'GET',
  })
}

export async function sendActuatorCommand(
  name: string,
  value: boolean
): Promise<ActuatorCommandResponse> {
  return apiClient<ActuatorCommandResponse>(`/api/actuators/${encodeURIComponent(name)}`, {
    method: 'POST',
    body: JSON.stringify({ value }),
  })
}
