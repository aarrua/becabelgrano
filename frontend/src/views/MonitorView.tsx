import { useQuery } from '@tanstack/react-query'
import { fetchLatestTelemetry } from '../api/telemetry'
import { TankVisualizer } from '../components/TankVisualizer'
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

interface MonitorViewProps {
  controlSlot?: React.ReactNode
}

export function MonitorView({ controlSlot }: MonitorViewProps) {
  const refetchInterval = Number(import.meta.env.VITE_TELEMETRY_REFETCH_INTERVAL_MS) || 2000

  const { data: telemetry, isLoading, error } = useQuery({
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

  const alarms = telemetry?.alarms ?? {}
  const hasAlarms = Boolean(alarms['overflow_a'] || alarms['overflow_b'] || alarms['sensor_fault'])

  return (
    <div className="monitor-container">
      {/* Barra superior de estado del sistema */}
      <section className="telemetry-bar">
        <div className="telemetry-bar-group">
          <div className="status-indicator">
            <span className="status-dot dot-online" />
            <span className="status-label">ESP32 Conectado</span>
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
                  ? 'Fallo de Sensores'
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

      {/* Visualizador Sinóptico de Tanques */}
      {telemetry && (
        <TankVisualizer
          tankA={telemetry.tank_a}
          tankB={telemetry.tank_b}
          flowLpm={telemetry.flow_lpm}
          alarms={alarms}
        />
      )}

      {/* Slot para Control de Bomba (rol DOCENTE / ALUMNO) */}
      {controlSlot && <div className="control-slot-wrapper">{controlSlot}</div>}

      {/* Dashboard Grafana Embebido */}
      <GrafanaEmbed />
    </div>
  )
}
