import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { sendActuatorCommand } from '../api/actuators'
import { useAuth } from '../context/AuthContext'
import { PumpIcon, FlowIcon, LockIcon, AlertTriangleIcon, CheckCircleIcon } from './Icons'
import { ApiError } from '../types/telemetry'

interface PumpControlProps {
  currentPumpState: boolean | null
  flowLpm?: number
  isInterlockBlocked?: boolean
  interlockReason?: string
}

function mapInterlockReason(reason?: string): string {
  if (!reason) return 'Comando rechazado por interlock de seguridad'
  if (reason.toLowerCase().includes('overflow_a')) {
    return 'Interlock de sobrellenado activo: Nivel crítico en Tanque A (> 85%)'
  }
  if (reason.toLowerCase().includes('overflow_b')) {
    return 'Interlock de sobrellenado activo: Nivel crítico en Tanque B (> 85%)'
  }
  if (reason.toLowerCase().includes('sensor_fault')) {
    return 'Interlock de seguridad activo: Falla o desconexión en sensores'
  }
  return `Comando rechazado por interlock: ${reason}`
}

export function PumpControl({
  currentPumpState,
  flowLpm = 0,
  isInterlockBlocked = false,
  interlockReason,
}: PumpControlProps) {
  const { role } = useAuth()
  const queryClient = useQueryClient()
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const mutation = useMutation({
    mutationFn: (targetState: boolean) => sendActuatorCommand('pump', targetState),
    onSuccess: (res) => {
      setFeedback({
        type: 'success',
        message: `Comando aplicado con éxito: Bomba ${res.value ? 'ENCENDIDA' : 'APAGADA'} (ack: ${res.ack})`,
      })
      queryClient.invalidateQueries({ queryKey: ['telemetry', 'latest'] })
      queryClient.invalidateQueries({ queryKey: ['actuators'] })
    },
    onError: (err: ApiError) => {
      if (err.status === 503 || err.reason === 'bridge_unavailable') {
        setFeedback({
          type: 'error',
          message: err.message || 'Control no disponible: sin conexión con el equipo',
        })
      } else if (err.status === 409) {
        setFeedback({
          type: 'error',
          message: mapInterlockReason(err.reason || err.message),
        })
      } else if (err.status === 403) {
        setFeedback({
          type: 'error',
          message: 'Acceso denegado: solo usuarios con rol DOCENTE pueden operar actuadores',
        })
      } else {
        setFeedback({
          type: 'error',
          message: err.message || 'Error al ejecutar comando sobre el actuador',
        })
      }
    },
  })

  const isDocente = role === 'DOCENTE'
  const isRunning = currentPumpState === true
  const isStopped = currentPumpState === false
  const isUnknown = currentPumpState === null

  const handleAction = (targetState: boolean) => {
    setFeedback(null)
    mutation.mutate(targetState)
  }

  return (
    <div className="pump-control-card">
      <div className="pump-control-header">
        <div className="pump-header-title">
          <div
            className={`pump-icon-avatar ${
              isRunning ? 'avatar-running' : isStopped ? 'avatar-stopped' : 'avatar-unknown'
            }`}
          >
            <PumpIcon width="24" height="24" />
          </div>
          <div>
            <h3 className="section-title">Bomba de Impulsión</h3>
            <p className="section-subtitle">
              {isDocente
                ? 'Control de actuador físico (Reservorio → Tanque A)'
                : 'Monitoreo de actuador (Reservorio → Tanque A)'}
            </p>
          </div>
        </div>

        <div className="pump-header-status">
          <div className="pump-flow-badge" title="Caudal medido en la impulsión">
            <FlowIcon width="16" height="16" />
            <span className="flow-badge-label">Caudal de entrada:</span>
            <span className="flow-badge-val">{flowLpm.toFixed(2)}</span>
            <span className="flow-badge-unit">L/min</span>
          </div>

          <span
            className={`pump-state-pill ${
              isRunning ? 'state-on' : isStopped ? 'state-off' : 'state-unknown'
            }`}
            title={isUnknown ? 'Sin telemetría reciente (> 5 s). Verifique la conexión con el equipo.' : undefined}
          >
            <span className="state-dot" />
            {isRunning ? 'ENCENDIDA' : isStopped ? 'APAGADA' : 'DESCONOCIDO'}
          </span>
        </div>
      </div>

      {/* Panel para rol ALUMNO (sin botonera) */}
      {!isDocente && (
        <div className="pump-readonly-info">
          <LockIcon width="16" height="16" />
          <span>
            Modo Observador (Rol <strong>ALUMNO</strong>): Visualización de estado en tiempo real sin botonera de control.
            El accionamiento de actuadores está reservado para docentes.
          </span>
        </div>
      )}

      {/* Panel para rol DOCENTE (con botonera interactiva) */}
      {isDocente && (
        <div className="pump-actions-area">
          {isInterlockBlocked && !isRunning && (
            <div className="alert-interlock-warning">
              <AlertTriangleIcon width="16" height="16" />
              <span>
                {interlockReason ? mapInterlockReason(interlockReason) : 'Interlock de sobrellenado activo (> 85%). Encendido bloqueado.'}
              </span>
            </div>
          )}

          {isUnknown && (
            <div className="alert-unknown-warning">
              <AlertTriangleIcon width="16" height="16" />
              <span>
                Estado de bomba no confirmado (sin telemetría reciente &gt; 5 s). Puede emitir comandos de control directamente al equipo.
              </span>
            </div>
          )}

          <div className="pump-button-row">
            {isUnknown ? (
              <div className="pump-buttons-dual">
                <button
                  onClick={() => handleAction(true)}
                  disabled={mutation.isPending || isInterlockBlocked}
                  className="btn-pump-toggle btn-pump-start"
                >
                  <PumpIcon width="18" height="18" />
                  <span>{mutation.isPending ? 'Transmitiendo...' : 'Forzar Encendido'}</span>
                </button>
                <button
                  onClick={() => handleAction(false)}
                  disabled={mutation.isPending}
                  className="btn-pump-toggle btn-pump-stop"
                >
                  <PumpIcon width="18" height="18" />
                  <span>{mutation.isPending ? 'Transmitiendo...' : 'Forzar Apagado'}</span>
                </button>
              </div>
            ) : (
              <button
                onClick={() => handleAction(!currentPumpState)}
                disabled={mutation.isPending || (isInterlockBlocked && !currentPumpState)}
                className={`btn-pump-toggle ${currentPumpState ? 'btn-pump-stop' : 'btn-pump-start'}`}
              >
                <PumpIcon width="18" height="18" />
                <span>
                  {mutation.isPending
                    ? 'Transmitiendo comando...'
                    : currentPumpState
                    ? 'Apagar Bomba'
                    : 'Encender Bomba'}
                </span>
              </button>
            )}
          </div>

          {feedback && (
            <div className={`pump-feedback-toast toast-${feedback.type}`}>
              {feedback.type === 'success' ? (
                <CheckCircleIcon width="18" height="18" />
              ) : (
                <AlertTriangleIcon width="18" height="18" />
              )}
              <span>{feedback.message}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
