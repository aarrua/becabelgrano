import { useQuery } from '@tanstack/react-query'
import { fetchLatestTelemetry } from '../api/telemetry'
import { TankVisualizer } from '../components/TankVisualizer'
import { PumpControl } from '../components/PumpControl'
import { GrafanaEmbed } from '../components/GrafanaEmbed'
import { ShieldAlertIcon, CheckCircleIcon, AlertTriangleIcon } from '../components/Icons'

function formatUptime(ms: number): string {
  if (!ms || ms < 0) return '0s'
  const seconds = Math.floor((ms / 1000) % 60)
  const minutes = Math.floor((ms / (1000 * 60)) % 60)
  const hours = Math.floor(ms / (1000 * 60 * 60))

  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

export function MonitorView() {
  const refetchInterval = Number(import.meta.env.VITE_TELEMETRY_REFETCH_INTERVAL_MS) || 2000

  const { data: telemetry, isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ['telemetry', 'latest'],
    queryFn: fetchLatestTelemetry,
    refetchInterval,
    refetchIntervalInBackground: true,
  })

  if (isLoading && !telemetry) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <p>Conectando con la planta de tanques...</p>
      </div>
    )
  }

  if (error && !telemetry) {
    return (
      <div className="alert-error" style={{ margin: '2rem 0' }}>
        <strong>Error de telemetría:</strong> No se pudo obtener el estado de la planta.
        Verifique la conexión con el backend en borde.
      </div>
    )
  }

  // Antigüedad y frescura de la telemetría
  const now = Date.now()
  const ageMs = dataUpdatedAt ? now - dataUpdatedAt : Infinity
  const isDisconnected = Boolean(error) || !telemetry || ageMs > 10000
  const isStale = !isDisconnected && (ageMs > 5000 || telemetry?.actuators?.['pump'] === null)

  const alarms = telemetry?.alarms ?? {}
  const hasAlarms = Boolean(
    alarms['overflow_a'] || alarms['overflow_b'] || alarms['sensor_fault'] || alarms['pump_timeout']
  )
  const pumpState = telemetry?.actuators?.['pump'] ?? null
  
  const tankALevel = telemetry?.tank_a?.level_pct ?? 0
  const tankBLevel = telemetry?.tank_b?.level_pct ?? 0
  const isOverflow = tankALevel >= 85.0 || tankBLevel >= 85.0 || alarms['overflow_a'] || alarms['overflow_b']
  const isInterlockBlocked = isOverflow || Boolean(alarms['sensor_fault'])

  let interlockReason: string | undefined
  if (alarms['sensor_fault']) interlockReason = 'sensor_fault'
  else if (tankALevel >= 85.0 || alarms['overflow_a']) interlockReason = 'overflow_a'
  else if (tankBLevel >= 85.0 || alarms['overflow_b']) interlockReason = 'overflow_b'

  return (
    <div className="monitor-container">
      {/* Barra superior de estado del sistema */}
      <section className="telemetry-bar">
        <div className="telemetry-bar-group">
          <div className="status-indicator">
            <span
              className={`status-dot ${
                isDisconnected ? 'dot-offline' : isStale ? 'dot-stale' : 'dot-online'
              }`}
            />
            <span className="status-label">
              {isDisconnected
                ? 'Equipo Desconectado'
                : isStale
                ? 'Sin datos recientes'
                : 'Equipo Conectado'}
            </span>
          </div>

          <div className="telemetry-badge">
            <span className="badge-name">Modo:</span>
            <span className="badge-val uppercase">{telemetry?.mode || 'AUTO'}</span>
          </div>

          <div className="telemetry-badge">
            <span className="badge-name">Trama #</span>
            <span className="badge-val">{telemetry?.seq ?? '--'}</span>
          </div>

          <div className="telemetry-badge">
            <span className="badge-name">Uptime:</span>
            <span className="badge-val">{formatUptime(telemetry?.uptime_ms ?? 0)}</span>
          </div>
        </div>

        <div className="telemetry-bar-group">
          {hasAlarms ? (
            <div className="alarm-indicator indicator-danger">
              <ShieldAlertIcon width="16" height="16" />
              <span>
                {alarms['sensor_fault']
                  ? 'Fallo de Sensores de Nivel'
                  : alarms['pump_timeout']
                  ? 'Bomba Apagada por Watchdog (60 s)'
                  : alarms['overflow_a'] || alarms['overflow_b']
                  ? 'Interlock de Sobrellenado Activo'
                  : 'Alarma Activa'}
              </span>
            </div>
          ) : (
            <div className="alarm-indicator indicator-ok">
              <CheckCircleIcon width="16" height="16" />
              <span>Interlocks Operativos &bull; Sin Alarmas</span>
            </div>
          )}
        </div>
      </section>

      {/* Alerta visible si hay fallo de sensor */}
      {alarms['sensor_fault'] && (
        <div className="alert-sensor-fault">
          <AlertTriangleIcon width="20" height="20" />
          <div>
            <strong>Alerta de Hardware:</strong> Se detectó falla o desconexión en los sensores de nivel.
            El control automático y manual se encuentra bloqueado por seguridad.
          </div>
        </div>
      )}

      {/* Alerta visible si hubo corte por timeout de bomba */}
      {alarms['pump_timeout'] && (
        <div className="alert-sensor-fault">
          <AlertTriangleIcon width="20" height="20" />
          <div>
            <strong>Watchdog de Seguridad de Bomba:</strong> La bomba de impulsión fue apagada automáticamente tras alcanzar el tiempo máximo de encendido continuo (60 segundos). Puede reactivarse con un nuevo comando cuando sea seguro.
          </div>
        </div>
      )}

      {/* Visualizador Sinóptico de Tanques */}
      {telemetry && (
        <TankVisualizer
          tankA={telemetry.tank_a}
          tankB={telemetry.tank_b}
          alarms={alarms}
        />
      )}

      {/* Panel de Control de Bomba (con caudal de entrada y comportamiento según rol) */}
      <PumpControl
        currentPumpState={pumpState}
        flowLpm={telemetry?.flow_lpm}
        isInterlockBlocked={isInterlockBlocked}
        interlockReason={interlockReason}
        isTelemetryStale={isStale}
      />

      {/* Dashboard Grafana Embebido */}
      <GrafanaEmbed />
    </div>
  )
}
