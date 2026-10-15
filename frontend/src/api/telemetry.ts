import { apiClient } from './client'
import { TelemetryFrame } from '../types/telemetry'

export async function fetchLatestTelemetry(): Promise<TelemetryFrame> {
  return apiClient<TelemetryFrame>('/api/telemetry/latest', {
    method: 'GET',
  })
}
