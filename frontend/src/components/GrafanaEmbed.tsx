interface GrafanaEmbedProps {
  url?: string
}

const DEFAULT_GRAFANA_URL =
  '/grafana/d/tanques-monitor/kit-didactico-de-tanques-interconectados?orgId=1&refresh=5s&kiosk'

function removeKioskParam(urlStr: string): string {
  try {
    const base = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
    const parsed = new URL(urlStr, base)
    parsed.searchParams.delete('kiosk')
    if (urlStr.startsWith('/')) {
      return parsed.pathname + (parsed.search ? parsed.search : '') + (parsed.hash ? parsed.hash : '')
    }
    return parsed.toString()
  } catch {
    return urlStr.replace(/[?&]kiosk(?:=[^&]*)?/g, '').replace(/\?$/, '')
  }
}

export function GrafanaEmbed({ url }: GrafanaEmbedProps) {
  const grafanaUrl = url || import.meta.env.VITE_GRAFANA_DASHBOARD_URL || DEFAULT_GRAFANA_URL
  const openUrl = removeKioskParam(grafanaUrl)

  return (
    <div className="grafana-section">
      <div className="grafana-header">
        <div>
          <h3 className="section-title">Dashboard Histórico de Métricas</h3>
          <p className="section-subtitle">Visualización embebida provista por Grafana &bull; InfluxDB</p>
        </div>
        <a
          href={openUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-external-link"
        >
          Abrir en Grafana &#8599;
        </a>
      </div>

      <div className="grafana-frame-wrapper">
        <iframe
          src={grafanaUrl}
          title="Grafana Dashboard Tanques"
          className="grafana-iframe"
          loading="lazy"
        />
      </div>
    </div>
  )
}
