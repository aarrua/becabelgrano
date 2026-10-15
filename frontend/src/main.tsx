import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// Defensa anti-anidamiento: no renderizar la aplicación si está dentro de un iframe
if (window.self === window.top) {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
} else {
  console.warn('Ejecución dentro de iframe bloqueada para evitar anidamiento recursivo de la SPA.')
}
