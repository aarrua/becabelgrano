/**
 * Especificación de Contrato de Datos - Kit Didáctico de Tanques Interconectados
 * Según docs/01-contrato-datos.md y modelos del backend Spring Boot
 */

export interface TankTelemetry {
  weight_g: number | null
  level_pct: number | null
  temp_c: number | null
}

export interface TelemetryFrame {
  v: number
  seq: number
  uptime_ms: number
  tank_a: TankTelemetry
  tank_b: TankTelemetry
  flow_lpm: number | null
  actuators: Record<string, boolean | null>
  alarms: Record<string, boolean>
  mode: string
}

export type UserRole = 'DOCENTE' | 'ALUMNO'

export interface UserResponse {
  username: string
  role: UserRole
}

export interface AuthResponse {
  token: string
  username: string
  role: UserRole
}

export interface ActuatorCommandRequest {
  value: boolean
}

export interface ActuatorCommandResponse {
  ack: string
  ok: boolean
  reason?: string | null
  message?: string | null
  target: string
  value: boolean
  timestamp: string
}

export interface AuditLogEntry {
  id: number
  username: string
  target: string
  requestedValue: boolean
  ok: boolean
  reason: string | null
  timestamp: string
}

export interface ApiError {
  status: number
  message: string
  reason?: string
}
