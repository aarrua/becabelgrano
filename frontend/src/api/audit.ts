import { apiClient } from './client'
import { AuditLogEntry } from '../types/telemetry'

export async function fetchAuditLogs(): Promise<AuditLogEntry[]> {
  return apiClient<AuditLogEntry[]>('/api/audit', {
    method: 'GET',
  })
}
