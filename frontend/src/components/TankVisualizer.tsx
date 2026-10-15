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

      <div className="cylinder-wrapper">
        <div className="cylinder-body">
          {/* Marcador umbral interlock 85% */}
          <div className="interlock-threshold-line" title="Umbral de corte de interlock (85%)">
            <span className="threshold-label">85% Interlock</span>
          </div>

          {/* Líquido */}
          <div
            className={`water-fill ${isHigh ? 'water-alert' : ''}`}
            style={{ height: `${level}%` }}
          >
            <div className="water-wave" />
          </div>

          {/* Marcas de porcentaje */}
          <div className="level-ticks">
            <div className="tick-mark t-100"><span>100%</span></div>
            <div className="tick-mark t-75"><span>75%</span></div>
            <div className="tick-mark t-50"><span>50%</span></div>
            <div className="tick-mark t-25"><span>25%</span></div>
            <div className="tick-mark t-0"><span>0%</span></div>
          </div>
        </div>

        {/* Nivel numérico central */}
        <div className="level-display">
          <span className="level-number">{level.toFixed(1)}</span>
          <span className="level-unit">%</span>
        </div>
      </div>

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
  flowLpm: number
  alarms: Record<string, boolean>
}

export function TankVisualizer({ tankA, tankB, flowLpm, alarms }: TankVisualizerProps) {
  return (
    <div className="synoptic-section">
      <div className="tanks-layout">
        {/* Tanque A */}
        <TankCylinder
          name="Tanque A"
          subtitle="Superior &bull; Impulsión"
          telemetry={tankA}
          isOverflow={Boolean(alarms['overflow_a'])}
          isAlarmActive={Boolean(alarms['overflow_a'])}
        />

        {/* Acoplamiento Hidráulico Central */}
        <div className="hydraulic-junction">
          <div className="junction-line" />
          <div className="junction-badge">
            <span className="junction-label">Descarga por Gravedad</span>
            <div className="flow-meter">
              <span className="flow-title">Caudal Impulsión</span>
              <span className="flow-value">{flowLpm.toFixed(2)}</span>
              <span className="flow-unit">L/min</span>
            </div>
          </div>
          <div className="junction-line" />
        </div>

        {/* Tanque B */}
        <TankCylinder
          name="Tanque B"
          subtitle="Inferior &bull; Intermedio"
          telemetry={tankB}
          isOverflow={Boolean(alarms['overflow_b'])}
          isAlarmActive={Boolean(alarms['overflow_b'])}
        />
      </div>
    </div>
  )
}
