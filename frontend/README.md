# Frontend SPA - Kit Didáctico de Tanques Interconectados

Plataforma web de monitoreo en tiempo real y control de actuadores para el kit de tanques acoplados (UTN FRSF / GITDA), diseñada para despliegue en el borde (*Edge Computing*) sobre Raspberry Pi.

---

## 1. Stack Tecnológico y Dependencias Fijadas

El frontend está desarrollado como una Single Page Application (SPA) con **versiones exactas y fijas** (sin prefijos `^` ni `~` en `package.json`):

| Dependencia | Versión Fija | Rol en la Arquitectura |
|---|:---:|---|
| **`react`** | `19.3.1` | Librería principal de renderizado y estado |
| **`react-dom`** | `19.3.1` | Adaptador DOM para React 19 |
| **`react-router`** | `7.18.4` | Enrutamiento declarativo cliente (`BrowserRouter`, `Routes`, `Route`) |
| **`@tanstack/react-query`** | `5.104.2` | Manejo de estado remoto y polling periódico |
| **`vite`** | `8.3.4` | Herramienta de compilación y servidor dev de alto rendimiento |
| **`@vitejs/plugin-react`** | `6.1.2` | Plugin oficial de React para Vite |
| **`typescript`** | `7.0.2` | Tipado estático estricto |
| **`@types/react`** | `19.3.0` | Definiciones TypeScript para React 19 |
| **`@types/react-dom`** | `19.3.0` | Definiciones TypeScript para ReactDOM 19 |
| **`@types/node`** | `24.19.2` | Tipos de Node alineados al entorno activo (Node 24.x) |

### Decisión de Arquitectura: React Router 7.18.4 vs 8.4.0
Se seleccionó deliberadamente **React Router `7.18.4`** en lugar de la versión `8.4.0` **por prudencia y estabilidad arquitectónica**:
- La línea **7.x** es la release LTS probada que mantiene soporte nativo y estable de primera clase para el **modo declarativo tradicional** (`<BrowserRouter>`, `<Routes>`, `<Route>`, `useNavigate`, `useLocation`) importado directamente desde el paquete `"react-router"`.
- Permite operar la aplicación como una SPA puramente cliente sin acoplarse al modo framework (SSR, loaders de servidor o convenciones de carpetas invasivas) y sin incompatibilidades con el ecosistema de React 19.

---

## 2. Estructura del Proyecto

```text
frontend/
├── index.html                  # Plantilla HTML base
├── package.json                # Dependencias fijadas exactas
├── package-lock.json           # Árbol reproducible de dependencias
├── tsconfig.json               # Configuración TypeScript
├── tsconfig.app.json           # Configuración de compilación de la app
├── tsconfig.node.json          # Configuración para scripts de Vite
├── vite.config.ts              # Configuración de Vite con proxy hacia /api
├── .env.example                # Variables de entorno documentadas
├── public/
│   └── favicon.svg             # Favicon vectorial
└── src/
    ├── main.tsx                # Punto de entrada (createRoot)
    ├── App.tsx                 # Rutas declarativas y QueryClientProvider
    ├── index.css               # Diseño industrial dark, variables CSS y animaciones
    ├── vite-env.d.ts           # Declaración de tipos para Vite
    ├── types/
    │   └── telemetry.ts        # Contratos estrictos según docs/01-contrato-datos.md
    ├── api/
    │   ├── client.ts           # Cliente HTTP con Bearer JWT y control de errores
    │   ├── auth.ts             # POST /api/auth/login y GET /api/me
    │   ├── telemetry.ts        # GET /api/telemetry/latest
    │   ├── actuators.ts        # GET /api/actuators y POST /api/actuators/{name}
    │   └── audit.ts            # GET /api/audit
    ├── context/
    │   └── AuthContext.tsx     # Contexto de autenticación en memoria + sessionStorage
    ├── components/
    │   ├── Navbar.tsx          # Barra superior con estado de usuario, rol y navegación
    │   ├── ProtectedRoute.tsx  # Guarda de navegación por autenticación y rol
    │   ├── TankVisualizer.tsx  # Sinóptico de Tanques A y B con niveles y métricas
    │   ├── PumpControl.tsx     # Botonera de control (DOCENTE) / Modo lectura (ALUMNO)
    │   ├── GrafanaEmbed.tsx    # Iframe responsivo para dashboard de Grafana
    │   ├── AuditTable.tsx      # Tabla de trazabilidad con filtros y buscador
    │   └── Icons.tsx           # Íconos SVG inline sin librerías externas
    └── views/
        ├── LoginView.tsx       # Acceso seguro sin credenciales expuestas
        ├── MonitorView.tsx     # Vista principal de monitoreo y control
        └── AuditView.tsx       # Vista exclusiva de auditoría de comandos
```

---

## 3. Comportamiento por Roles de Usuario

| Funcionalidad | Rol `ALUMNO` | Rol `DOCENTE` |
|---|:---:|:---:|
| **Acceso a Monitoreo** (`/monitor`) | Sí (Lectura) | Sí (Lectura y Control) |
| **Visualización Sinóptica de Tanques** | Sí (Niveles, caudales, masas, temps) | Sí (Niveles, caudales, masas, temps) |
| **Dashboard de Grafana** | Sí | Sí |
| **Botonera de Control de Bomba** | **Oculta** (Cartel de Modo Observador) | **Visible** (Encender / Apagar con feedback) |
| **Acceso a Auditoría** (`/audit`) | **Bloqueado** (Redirige a `/monitor`) | **Permitido** (Trazabilidad completa) |

---

## 4. Manejo Semántico de Errores en Actuadores

Al enviar un comando sobre un actuador desde la UI, el sistema traduce los códigos HTTP:
- **HTTP 503 (`reason: "bridge_unavailable"`)**: `"Control no disponible: sin conexión con el equipo"` (informa al usuario que el hardware o canal serial no está disponible en producción).
- **HTTP 409 (`InterlockViolationException`)**: Muestra el motivo específico del interlock (ej. sobrellenado $> 85\%$ o falla en sensores).
- **HTTP 403**: `"Acceso denegado: solo usuarios con rol DOCENTE pueden operar actuadores"`.

---

## 5. Instrucciones de Ejecución

### Desarrollo Local
```bash
# Instalar dependencias exactas
npm install

# Iniciar servidor de desarrollo en http://localhost:5173
npm run dev
```
> En desarrollo, las llamadas a `/api/*` se redirigen automáticamente mediante el proxy de Vite a `http://localhost:8080`.

### Compilación para Producción
```bash
npm run build
```
Genera los archivos estáticos listos para ser servidos por **nginx** en `frontend/dist/`.
