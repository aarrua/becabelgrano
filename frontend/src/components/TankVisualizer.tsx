import { TankTelemetry } from '../types/telemetry'
import { ThermometerIcon, ScaleIcon, AlertTriangleIcon, CheckCircleIcon } from './Icons'

interface TankProps {
  name: string
  subtitle: string
  telemetry: TankTelemetry
  isOverflow: boolean
  isAlarmActive: boolean
}

function TankCylinder({ name, subtitle, telemetry, isOverflow, isAlarmActive }: TankProps) {
  const level = Math.max(0, Math.min(100, telemetry.level_pct ?? 0))
  const isHigh = level >= 85.0 || isOverflow || isAlarmActive

  return (
    <div className={`tank-card ${isHigh ? 'tank-warning' : ''}`}>
      <div className="tank-card-header">
        <div>
          <h3 className="tank-name">{name}</h3>
          <span className="tank-subtitle">{subtitle}</span>
        </div>
        <div className={`tank-status-pill ${isHigh ? 'pill-alert' : 'pill-ok'}`}>
          {isHigh ? (
            <>
              <AlertTriangleIcon width="14" height="14" />
              <span>{level >= 85.0 ? 'Sobrellenado' : 'Alarma'}</span>
            </>
          ) : (
            <>
              <CheckCircleIcon width="14" height="14" />
              <span>Normal</span>
            </>
          )}
        </div>
      </div>

      {/* Lectura digital destacada de nivel (sin superposición en la escala) */}
      <div className="tank-level-banner">
        <span className="level-banner-label">Nivel útil</span>
        <div className="level-banner-digits">
          <span className={`level-number ${isHigh ? 'text-alert' : ''}`}>
            {level.toFixed(1)}
          </span>
          <span className="level-unit">%</span>
        </div>
      </div>

      {/* Contenedor del cilindro con escala graduada lateral libre de recortes */}
      <div className="cylinder-visualizer-container">
        {/* Escala graduada a la izquierda (fuera del contenedor con overflow) */}
        <div className="ruler-scale">
          <div className="ruler-mark r-100">
            <span className="ruler-label">100%</span>
            <span className="ruler-tick" />
          </div>
          <div className="ruler-mark r-85">
            <span className="ruler-label ruler-label-alert">85%</span>
            <span className="ruler-tick ruler-tick-alert" />
          </div>
          <div className="ruler-mark r-75">
            <span className="ruler-label">75%</span>
            <span className="ruler-tick" />
          </div>
          <div className="ruler-mark r-50">
            <span className="ruler-label">50%</span>
            <span className="ruler-tick" />
          </div>
          <div className="ruler-mark r-25">
            <span className="ruler-label">25%</span>
            <span className="ruler-tick" />
          </div>
          <div className="ruler-mark r-0">
            <span className="ruler-label">0%</span>
            <span className="ruler-tick" />
          </div>
        </div>

        {/* Cilindro transparente con líquido */}
        <div className="cylinder-body">
          {/* Línea de umbral de interlock al 85% */}
          <div className="interlock-threshold-line" title="Umbral de corte de interlock (85.0%)">
            <span className="threshold-tag">Corte 85%</span>
          </div>

          {/* Nivel de fluido */}
          <div
            className={`water-fill ${isHigh ? 'water-alert' : ''}`}
            style={{ height: `${level}%` }}
          >
            <div className="water-wave" />
          </div>
        </div>
      </div>

      {/* Métricas de masa y temperatura */}
      <div className="tank-metrics-grid">
        <div className="metric-box">
          <div className="metric-header">
            <ScaleIcon width="15" height="15" />
            <span>Masa</span>
          </div>
          <div className="metric-value">
            {telemetry.weight_g != null ? telemetry.weight_g.toFixed(1) : '--'}
            <span className="unit"> g</span>
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-header">
            <ThermometerIcon width="15" height="15" />
            <span>Temperatura</span>
          </div>
          <div className="metric-value">
            {telemetry.temp_c != null ? telemetry.temp_c.toFixed(1) : '--'}
            <span className="unit"> °C</span>
          </div>
        </div>
      </div>
    </div>
  )
}

interface TankVisualizerProps {
  tankA: TankTelemetry
  tankB: TankTelemetry
  alarms: Record<string, boolean>
}

export function TankVisualizer({ tankA, tankB, alarms }: TankVisualizerProps) {
  return (
    <div className="synoptic-section">
      <div className="tanks-layout">
        {/* Tanque A */}
        <TankCylinder
          name="Tanque A"
          subtitle="Superior &bull; Entrada de Impulsión"
          telemetry={tankA}
          isOverflow={Boolean(alarms['overflow_a'])}
          isAlarmActive={Boolean(alarms['overflow_a'])}
        />

        {/* Acoplamiento Hidráulico Central (descarga por gravedad A -> B) */}
        <div className="hydraulic-junction">
          <div className="junction-line" />
          <div className="junction-badge">
            <span className="junction-label">Descarga por Gravedad</span>
            <span className="junction-path">Tanque A &rarr; Tanque B</span>
          </div>
          <div className="junction-line" />
        </div>

        {/* Tanque B */}
        <TankCylinder
          name="Tanque B"
          subtitle="Inferior &bull; Salida a Reservorio"
          telemetry={tankB}
          isOverflow={Boolean(alarms['overflow_b'])}
          isAlarmActive={Boolean(alarms['overflow_b'])}
        />
      </div>
    </div>
  )
}
