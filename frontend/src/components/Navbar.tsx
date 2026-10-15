import { Link, useLocation } from 'react-router'
import { useAuth } from '../context/AuthContext'
import { TankIcon, HistoryIcon, LogOutIcon, UserIcon } from './Icons'

export function Navbar() {
  const { user, role, logout } = useAuth()
  const location = useLocation()

  return (
    <header className="navbar">
      <div className="navbar-container">
        <Link to="/monitor" className="navbar-brand">
          <TankIcon stroke="var(--accent-cyan)" width="24" height="24" />
          <span className="brand-title">Tanques Didácticos</span>
          <span className="brand-tag">FRSF</span>
        </Link>

        <nav className="navbar-nav">
          <Link
            to="/monitor"
            className={`nav-link ${location.pathname === '/monitor' ? 'active' : ''}`}
          >
            Monitoreo
          </Link>

          {role === 'DOCENTE' && (
            <Link
              to="/audit"
              className={`nav-link ${location.pathname === '/audit' ? 'active' : ''}`}
            >
              <HistoryIcon width="16" height="16" />
              <span>Auditoría</span>
            </Link>
          )}
        </nav>

        <div className="navbar-user">
          <div className="user-info">
            <UserIcon width="16" height="16" />
            <span className="username">{user?.username}</span>
            <span className={`role-badge role-${role?.toLowerCase()}`}>
              {role}
            </span>
          </div>

          <button onClick={logout} className="btn-logout" title="Cerrar sesión" aria-label="Cerrar sesión">
            <LogOutIcon width="18" height="18" />
            <span className="logout-text">Salir</span>
          </button>
        </div>
      </div>
    </header>
  )
}
