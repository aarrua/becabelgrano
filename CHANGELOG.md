# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto adhiere a [Conventional Commits](https://www.conventionalcommits.org/).

---

## [Unreleased]

### Planned (Fase 4 - Puesta en Marcha Integral, Integración en Producción y Firmware)
- Prueba y validación del backend en perfil `prod` contra InfluxDB 2.x (`InfluxTelemetryProvider`) y verificación de consistencia con los dashboards de Grafana.
- Despliegue de los artefactos estáticos compilados de la SPA (`frontend/dist/`) en el contenedor Nginx en la raíz `/`.
- Implementación del canal bidireccional de comandos en `edge/bridge.py` (listener local) para despacho serial hacia el ESP32 / simulador y resolución de `BridgeActuatorGateway` (503).
- Firmware definitivo para ESP32 con contrato JSON v1, parser de comandos e interlocks de hardware de última barrera.
- Calibración del umbral de interlock del 85% con el kit físico y evaluación de corte por volumen total combinado (A+B).
- Ajuste del formato de decimales en los gauges del dashboard de Grafana (`Decimals = 1`).
- Etiqueta dinámica de conexión en la SPA según timestamp de última trama recibida (> 5 s sin datos).
- Incorporación homogénea del campo `target` en todos los modelos de auditoría.
- Validación visual de diseño en dispositivos móviles reales.

---


## [Fase 3 - Frontend SPA, Monitoreo y Control por Roles] - 2026-10-15

### Added
- **Single Page Application en React 19 y Vite**:
  - Implementación moderna con React `19.3.1`, Vite `8.3.4`, TypeScript `7.0.2` y `@types/node 24.19.2`.
  - Enrutamiento declarativo cliente con **React Router `7.18.4`** (`BrowserRouter`, `Routes`, `Route`, `Navigate`) importado desde `"react-router"`.
  - Polling periódico de telemetría en tiempo real con **TanStack Query v5 (`5.104.2`)** mediante hook `useQuery` con intervalo configurable por entorno (`VITE_TELEMETRY_REFETCH_INTERVAL_MS`).
  - Contexto de autenticación JWT (`AuthContext`) con persistencia en memoria y respaldo en `sessionStorage`, y cierre de sesión automático ante respuestas 401.
  - Guarda de navegación `ProtectedRoute` para control de acceso y redirección por rol (`DOCENTE` vs `ALUMNO`).
  - Vista sinóptica gráfica animada (`TankVisualizer`) con cilindros de agua proporcionales, marcas de nivel, línea de umbral de interlock del 85%, métricas de masa (`weight_g`), caudal (`flow_lpm`) y temperatura (`temp_c`).
  - Panel de control de bomba de impulsión (`PumpControl`) exclusivo para rol `DOCENTE`, con mutación asíncrona mediante `useMutation` e invalidación automática de queries.
  - Modo observador de solo lectura para rol `ALUMNO`: oculta la botonera de control y el enlace a auditoría.
  - Mapeo semántico de errores en control de actuadores:
    - HTTP 503 (`reason: "bridge_unavailable"`): *"Control no disponible: sin conexión con el equipo"*.
    - HTTP 409 (`InterlockViolationException`): Exposición legible del motivo de rechazo por sobrellenado o falla de sensor.
    - HTTP 403: *"Acceso denegado: solo usuarios con rol DOCENTE pueden operar actuadores"*.
  - Vista de auditoría histórica (`AuditView` y `AuditTable`) exclusiva para `DOCENTE`, con filtrado por resultado (Todos, Aceptados, Rechazados) y buscador de eventos.
  - Dashboard histórico embebido de Grafana (`GrafanaEmbed`) con URL configurable por variable de entorno `VITE_GRAFANA_DASHBOARD_URL`.
  - Colección de íconos SVG inline (`Icons.tsx`) y diseño industrial dark personalizado con CSS plano (`index.css`) responsivo para dispositivos móviles y escritorio.

### Changed
- Fijadas versiones exactas y estrictas en `frontend/package.json` (sin rangos `^` ni `~`) y versionado de `package-lock.json`.
- Documentada la justificación arquitectónica de adopción de React Router 7.18.4 frente a 8.4.0 en `frontend/README.md` y `AGENTS.md`.

### Fixed
- **Proxy de Grafana y prevención de anidamiento de iframes**:
  - Configurado proxy para `/grafana` en `vite.config.ts` hacia `http://localhost` (Nginx en infra), resolviendo el bucle de iframes donde la SPA se servía a sí misma.
  - Implementada defensa anti-anidamiento en `main.tsx` validando `window.self === window.top`.
  - Normalizado enlace "Abrir en Grafana" para remover el parámetro `kiosk` manteniendo la URL del dashboard.
- **Corrección de textos y dirección de impulsión**:
  - Reemplazado `&rarr;` literal por flecha unicode y corregida la dirección hidráulica a `Reservorio → Tanque A`.
  - Reubicado el indicador de caudal de impulsión como "Caudal de entrada" en la tarjeta de la bomba, liberando la unión central de los tanques para representar exclusivamente la descarga por gravedad (`Tanque A → Tanque B`).
- **Rediseño del sinóptico de tanques (`TankVisualizer`)**:
  - Extraída la escala graduada fuera del contenedor del cilindro para evitar recortes de texto en las marcas (100%, 85%, 75%, 50%, 25%, 0%).
  - Trasladada la lectura digital porcentual de nivel a un encabezado dedicado superior, evitando la superposición sobre la columna de líquido y las marcas de nivel.



## [Fase 2 - Backend REST, Seguridad JWT y Auditoría] - 2026-10-15

### Added
- **Backend Spring Boot 3.5.16**: Aplicación REST modularizada en Java 21 bajo el paquete `ar.edu.utn.frsf.tanques`.
- **Seguridad Stateless JWT (JJWT 0.12.6)**:
  - Autenticación mediante `POST /api/auth/login` y verificación de claims en `GET /api/me`.
  - Control de acceso basado en roles (RBAC): `DOCENTE` (permisos de control de actuadores y visualización de auditoría) y `ALUMNO` (exclusivamente lectura).
  - Filtro `JwtAuthenticationFilter` y codificación de contraseñas con `BCryptPasswordEncoder`.
  - Validación de arranque de longitud mínima del secreto JWT ($\ge$ 32 caracteres / 256 bits).
- **Persistencia H2 en Disco (`./data/`)**:
  - Entidad `User` con precarga de usuarios semilla en arranque.
  - Entidad `CommandAuditEvent` para registrar cada intento de comando sobre actuadores (usuario, target, valor solicitado, resultado exitoso/rechazado, motivo y timestamp).
  - Modo archivo con soporte `AUTO_SERVER=TRUE` en `jdbc:h2:file:./data/tanquesdb`.
- **Documentación OpenAPI 3 / Swagger UI (`springdoc 2.8.16`)**:
  - Explorador interactivo expuesto en `/swagger-ui.html` y especificación OpenAPI en `/v3/api-docs`.
- **Control de Actuadores y Telemetría**:
  - `GET /api/telemetry/latest`: Entrega de trama de telemetría física normalizada idéntica al contrato de datos.
  - `GET /api/actuators`: Mapa extensible de estado de actuadores (`Map<String, Boolean>`).
  - `POST /api/actuators/{name}`: Endpoint custodiado por `@PreAuthorize("hasRole('DOCENTE')")` con validación previa de interlocks físicos.
  - `GET /api/audit`: Endpoint histórico de auditoría custodiado para rol `DOCENTE`.
- **Arquitectura de Gateways y Proveedores por Perfil**:
  - `MockActuatorGateway` y `MockTelemetryProvider` (perfil `dev`): Operación 100% autónoma en memoria con emulación física por Torricelli, sin requerir Docker ni hardware.
  - `BridgeActuatorGateway` e `InfluxTelemetryProvider` (perfil `prod`): Integración con InfluxDB 2.x mediante `influxdb-client-java 7.2.0` y desacoplamiento para el canal de borde.
- **Manejo Global de Errores Semánticos**:
  - `401 Unauthorized`: Peticiones sin token o credenciales inválidas.
  - `403 Forbidden`: Acceso de `ALUMNO` a endpoints restringidos.
  - `404 Not Found`: Actuadores no registrados en el gateway.
  - `409 Conflict`: Disparo de interlocks de seguridad (`InterlockViolationException`).
  - `503 Service Unavailable`: Falta de canal hacia el bridge (`BridgeUnavailableException`).
- **Pruebas Automatizadas**:
  - 25 tests unitarios y de integración con MockMvc en JUnit 5 / Spring Boot Test (100% PASS).
  - Documentación técnica detallada de la API en `docs/03-api.md`.

### Changed
- **Umbral de Interlock Reducido a 85%**: Configurado por defecto a `85.0%` en `edge/config.yaml` y `application.yml` para compensar la inercia del drenaje de Tanque A hacia Tanque B y asegurar que ningún tanque supere el 99% de capacidad.
- **Rechazo Explícito en Prod (503)**: `BridgeActuatorGateway` en perfil producción audita los comandos como rechazados y retorna HTTP 503 (`bridge_unavailable`) mientras no se implemente el listener serial en `edge/bridge.py`.
- **Reglas de Contraseñas en Prod**: Eliminados valores por defecto para `DOCENTE_PASSWORD` y `ALUMNO_PASSWORD`; en producción deben definirse obligatoriamente en variables de entorno o la aplicación interrumpe su inicialización.

### Fixed
- Corregida la respuesta del contrato de telemetría para asegurar que `tank_a` y `tank_b` incluyan invariablemente valores no nulos en `weight_g`, `level_pct` y `temp_c`.
- Restablecimiento automático de alarmas de sobrellenado en `MockTelemetryProvider` cuando los niveles descienden por debajo del umbral de corte.
- Exclusión en `.gitignore` de archivos generados por H2 en `./data/`.

---

## [Fase 1 - Simulación Física y Pipeline InfluxDB / Grafana] - 2026-10-15

### Added
- **Simulador Físico en Python (`edge/simulator.py`)**:
  - Simulación de dos tanques acoplados en serie con drenaje por ley de Torricelli.
  - Dinámica térmica pasiva (enfriamiento newtoniano hacia temperatura ambiente).
  - Corte de bomba automático por interlock de sobrellenado al superar el umbral porcentual.
  - Inyección de ruido instrumental gaussiano en mediciones de peso, caudal y temperatura.
  - Hilo de escucha de comandos JSON vía `sys.stdin`.
- **Bridge Serial e Ingesta Temporal (`edge/bridge.py`)**:
  - Lectura continua de tramas seriales o simulación interna en subproceso.
  - Sellado de tiempo oficial (*timestamping UTC*) en el borde.
  - Traducción de tramas JSON al Line Protocol de InfluxDB.
  - Mecanismo de reintento resiliente con backoff exponencial.
- **Infraestructura con Docker Compose (`infra/docker-compose.yml`)**:
  - InfluxDB 2.7 con inicialización automatizada de organización (`utn-frsf`) y bucket (`tanques`).
  - Grafana 11.2 con aprovisionamiento declarativo de data source InfluxDB (Flux) y dashboards.
  - Proxy Nginx exponiendo el punto único de entrada del sistema en el puerto `:80`.
- **Dashboard Didáctico en Grafana**:
  - Paneles temporales para niveles de tanques, temperaturas y caudal.
  - Indicadores de estado de bomba de impulsión e interlocks de sobrellenado.
- **Opción de Arranque `--pump-on`**:
  - Flag en simulador y bridge para inicializar la simulación con bomba encendida facilitando pruebas de interlocks.
- **Suite de Pruebas Python**:
  - 10 tests automatizados con `unittest` validando física, formateo a InfluxDB y cortes de seguridad.

### Fixed
- Resolución de rutas de `simulator.py` y `config.yaml` relativas a la ubicación del script con `Path(__file__).resolve().parent`.
- Ejecución del subproceso del simulador utilizando `sys.executable` para portabilidad entre entornos y plataformas.
- Mapeo de campos booleanos (`pump`, `overflow_a`, `overflow_b`, `sensor_fault`) a valores numéricos en queries Flux de Grafana y configuración de value mappings (1/0) para evitar visualizaciones vacías ("No data").

---

## [Fase 0 - Arquitectura Base y Contratos] - 2026-10-15

### Added
- Inicialización de estructura del repositorio y reglas de exclusión en `.gitignore`.
- Documento de convenciones del proyecto y restricciones de diseño en `AGENTS.md`.
- Especificación canónica del contrato de telemetría y comunicación serial UART (115200 8N1) en `docs/01-contrato-datos.md`.
- Especificación del flujo de comandos, matriz de defensa en profundidad e interlocks en `docs/02-flujo-comandos.md`.
- Delimitación de alcance estricta: exclusión de placas Peltier y actuadores de válvulas (válvulas manuales).
