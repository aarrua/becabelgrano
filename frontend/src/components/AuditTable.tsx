import { useState, useMemo } from 'react'
import { AuditLogEntry } from '../types/telemetry'
import { CheckCircleIcon, AlertTriangleIcon, HistoryIcon } from './Icons'

interface AuditTableProps {
  logs: AuditLogEntry[]
  isLoading?: boolean
}

function formatTimestamp(isoString: string): string {
  try {
    const d = new Date(isoString)
    return d.toLocaleString('es-AR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return isoString
  }
}

export function AuditTable({ logs, isLoading }: AuditTableProps) {
  const [filter, setFilter] = useState<'all' | 'accepted' | 'rejected'>('all')
  const [searchTerm, setSearchTerm] = useState('')

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const matchesFilter =
        filter === 'all' ? true : filter === 'accepted' ? log.ok : !log.ok

      const term = searchTerm.toLowerCase().trim()
      const matchesSearch =
        !term ||
        log.username.toLowerCase().includes(term) ||
        (log.target && log.target.toLowerCase().includes(term)) ||
        (log.reason && log.reason.toLowerCase().includes(term))

      return matchesFilter && matchesSearch
    })
  }, [logs, filter, searchTerm])

  if (isLoading) {
    return (
      <div className="audit-loading">
        <div className="spinner" />
        <p>Cargando eventos de auditoría...</p>
      </div>
    )
  }

  return (
    <div className="audit-card">
      <div className="audit-toolbar">
        <div className="filter-pills">
          <button
            onClick={() => setFilter('all')}
            className={`filter-pill ${filter === 'all' ? 'active' : ''}`}
          >
            Todos ({logs.length})
          </button>
          <button
            onClick={() => setFilter('accepted')}
            className={`filter-pill ${filter === 'accepted' ? 'active' : ''}`}
          >
            Aceptados ({logs.filter((l) => l.ok).length})
          </button>
          <button
            onClick={() => setFilter('rejected')}
            className={`filter-pill ${filter === 'rejected' ? 'active' : ''}`}
          >
            Rechazados ({logs.filter((l) => !l.ok).length})
          </button>
        </div>

        <div className="search-box">
          <input
            type="text"
            placeholder="Buscar por usuario o motivo..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
      </div>

      <div className="audit-table-wrapper">
        <table className="audit-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Fecha y Hora</th>
              <th>Usuario</th>
              <th>Actuador</th>
              <th>Acción</th>
              <th>Resultado</th>
              <th>Motivo / Razón</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-row">
                  <div className="empty-state">
                    <HistoryIcon width="28" height="28" />
                    <span>No se encontraron eventos de auditoría registrados.</span>
                  </div>
                </td>
              </tr>
            ) : (
              filteredLogs.map((log) => (
                <tr key={log.id} className={log.ok ? 'row-accepted' : 'row-rejected'}>
                  <td className="cell-id">#{log.id}</td>
                  <td className="cell-time">{formatTimestamp(log.timestamp)}</td>
                  <td className="cell-user">
                    <span className="user-tag">{log.username}</span>
                  </td>
                  <td className="cell-target">
                    <code>{log.target || 'pump'}</code>
                  </td>
                  <td className="cell-action">
                    <span className={`action-pill ${log.requestedValue ? 'action-on' : 'action-off'}`}>
                      {log.requestedValue ? 'ENCENDER' : 'APAGAR'}
                    </span>
                  </td>
                  <td className="cell-status">
                    <span className={`status-pill ${log.ok ? 'pill-ok' : 'pill-alert'}`}>
                      {log.ok ? (
                        <>
                          <CheckCircleIcon width="13" height="13" />
                          <span>Aceptado</span>
                        </>
                      ) : (
                        <>
                          <AlertTriangleIcon width="13" height="13" />
                          <span>Rechazado</span>
                        </>
                      )}
                    </span>
                  </td>
                  <td className="cell-reason">
                    {log.reason ? (
                      <span className="reason-text">{log.reason}</span>
                    ) : (
                      <span className="reason-none">&mdash;</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
