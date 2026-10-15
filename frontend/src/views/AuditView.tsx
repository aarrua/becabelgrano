import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAuditLogs } from '../api/audit'
import { AuditTable } from '../components/AuditTable'
import { HistoryIcon, RefreshIcon } from '../components/Icons'

export function AuditView() {
  const queryClient = useQueryClient()

  const { data: logs = [], isLoading, isFetching, error } = useQuery({
    queryKey: ['audit'],
    queryFn: fetchAuditLogs,
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['audit'] })
  }

  return (
    <div className="audit-view-container">
      <div className="view-header">
        <div>
          <div className="view-badge">
            <HistoryIcon width="16" height="16" />
            <span>Registro Oficial de Seguridad</span>
          </div>
          <h1 className="view-title">Historial de Auditoría</h1>
          <p className="view-subtitle">
            Trazabilidad completa de comandos ejecutados sobre actuadores físicos por usuarios con rol DOCENTE.
          </p>
        </div>

        <button
          onClick={handleRefresh}
          disabled={isFetching}
          className="btn-refresh"
          title="Refrescar lista"
        >
          <RefreshIcon width="16" height="16" />
          <span>{isFetching ? 'Actualizando...' : 'Refrescar'}</span>
        </button>
      </div>

      {error ? (
        <div className="alert-error">
          Error al cargar los registros de auditoría. Verifique los permisos de su sesión.
        </div>
      ) : (
        <AuditTable logs={logs} isLoading={isLoading} />
      )}
    </div>
  )
}
