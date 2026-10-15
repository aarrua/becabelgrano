# Convenciones y Guía del Proyecto (AGENTS.md)

> **AVISO OBLIGATORIO PARA AGENTES / DESARROLLADORES:**
> Lee este documento detenidamente **antes de iniciar cualquier tarea o fase**. Todas las decisiones arquitectónicas, convenciones de código, límites de alcance y estándares de versionado detallados aquí son de cumplimiento estricto.

---

## 1. Contexto y Objetivos del Proyecto

- **Institución**: Universidad Tecnológica Nacional - Facultad Regional Santa Fe (UTN FRSF) / GITDA.
- **Proyecto**: Kit didáctico de tanques interconectados para experimentación en IoT e Industria 4.0.
- **Objetivo**: Proveer una plataforma web completa de monitoreo en tiempo real y control seguro de actuadores, desplegada íntegramente en el borde (*Edge Computing*) sobre una Raspberry Pi, sin dependencia de servicios en la nube.
- **Restricción de plazo**: Priorizar un MVP funcional de punta a punta, robusto y testeable con datos simulados antes que complejidades innecesarias.

---

## 2. Decisiones de Arquitectura (Inmutables)

La arquitectura general está definida y no debe alterarse:

1. **Pipeline de Telemetría**:
   `ESP32` $\xrightarrow{\text{Serial JSON 115200}}$ `edge/bridge.py (Python)` $\xrightarrow{\text{Line Protocol}}$ `InfluxDB 2.x` $\xrightarrow{}$ `Grafana (paneles embebidos por iframe)`
2. **Pipeline de Control**:
   `Frontend (React)` $\xrightarrow{\text{HTTP REST /api}}$ `nginx` $\xrightarrow{\text{Proxy}}$ `Spring Boot` $\xrightarrow{}$ `ActuatorGateway` $\xrightarrow{}$ `Bridge` $\xrightarrow{\text{Serial JSON}}$ `ESP32`
3. **Punto de Entrada Único**:
   Un único servidor **nginx** expone:
   - `/`: Frontend web (build estático de React).
   - `/api`: Backend REST (Spring Boot).
   - `/grafana`: Visualización de métricas temporales (Grafana con embedding habilitado y rol Viewer anónimo).
4. **Backend (Stack y Versiones Homologadas)**:
   - Java 21 LTS, Maven.
   - **Spring Boot**: `3.5.16` (línea 3.5.x estable de soporte vigente; no usar Boot 4.x).
   - **OpenAPI 3 / Swagger UI**: `springdoc-openapi-starter-webmvc-ui: 2.8.16`.
   - **JWT**: `io.jsonwebtoken:jjwt-* 0.12.6`.
   - **InfluxDB Client**: `com.influxdb:influxdb-client-java 7.2.0`.
   - Seguridad con JWT stateless. Roles: `DOCENTE` (permisos de control de actuadores y auditoría) y `ALUMNO` (solo lectura).
   - Persistencia de usuarios y eventos de auditoría en base de datos H2 en disco (`./data/tanquesdb` con `AUTO_SERVER=TRUE`).
   - Documentación viva de endpoints mediante OpenAPI 3 expuesta en `/swagger-ui.html` y `/v3/api-docs`.
   - Aislamiento de perfiles: en perfil `dev` el backend corre localmente **sin Docker y sin ESP32** (con mocks en memoria sincronizados).
5. **Timestamping**:
   El ESP32 no tiene RTC. La Raspberry Pi asigna el timestamp oficial al momento de recibir la trama JSON e insertarla en InfluxDB.
6. **Geometría Configurable**:
   El área transversal de cada tanque (cilindros de distintos diámetros) y los factores de conversión deben residir en archivos de configuración (`edge/config.yaml` / `application.yml`), nunca hardcodeados.
7. **Diseño Extensible de Actuadores**:
   Actualmente el único actuador físico es la bomba (`pump`). El sistema modela el estado de actuadores como un mapa extensible (`Map<String, Boolean>`) y desacopla la validación de targets para que agregar nuevos actuadores futuros no requiera modificar la arquitectura.
8. **Reglas Estrictas de Configuración en Producción (`prod`)**:
   - El secreto JWT (`JWT_SECRET`) es obligatorio, sin valor por defecto y con longitud mínima de 32 caracteres (256 bits).
   - Las contraseñas iniciales de `DOCENTE` y `ALUMNO` en producción deben definirse obligatoriamente en `${DOCENTE_PASSWORD}` y `${ALUMNO_PASSWORD}` sin fallbacks por defecto; la aplicación aborta su arranque si faltan.
   - `BridgeActuatorGateway` en prod retorna HTTP `503 Service Unavailable` (`reason: "bridge_unavailable"`) y audita el rechazo mientras no exista el canal de comandos real hacia el bridge. No mantiene estado ficticio en memoria (su estado se deriva de la última telemetría).
9. **Umbral de Interlock de Sobrellenado**:
   - Configurado por defecto a **`85.0%`** (`overflow_threshold_pct: 85.0`) tanto en `edge/config.yaml` como en `application.yml`.
   - Permite compensar la inercia del volumen que continúa descargando el Tanque A hacia el Tanque B una vez apagada la bomba, garantizando que el Tanque B no supere el 99% de capacidad.

---

## 3. Delimitación de Alcance (Scope Boundaries)

- **FUERA DE ALCANCE (ESTRICTO)**: Placas Peltier, celdas de efecto termoeléctrico y cualquier mecanismo de control térmico activo. La temperatura registrada en los tanques es exclusivamente de **monitoreo pasivo**. No modelar, documentar, simular ni implementar nada relacionado con Peltier.
- **Válvulas**: Las llaves de paso entre los tanques y hacia el reservorio son manuales. No existe sensado ni control de válvulas en el protocolo.
- **Plataforma de despliegue**: Raspberry Pi (local). No se utilizan servicios en la nube (AWS, Azure, etc.).

---

## 4. Convenciones de Git y Control de Versiones

### 4.1 Conventional Commits
Cada commit debe respetar la especificación [Conventional Commits](https://www.conventionalcommits.org/):

```text
<tipo>(<alcance>): <descripción concisa en imperativo>

[cuerpo opcional detallando motivación y cambios]
```

- **Tipos permitidos**:
  - `feat`: Nueva funcionalidad para el usuario/sistema.
  - `fix`: Corrección de un bug o falla de comportamiento.
  - `docs`: Modificación o agregado de documentación.
  - `style`: Formateo de código sin cambio de lógica.
  - `refactor`: Reestructuración de código que no agrega funcionalidad ni arregla bugs.
  - `test`: Incorporación o corrección de pruebas automatizadas.
  - `chore`: Tareas de mantenimiento, dependencias o configuración del repositorio.
- **Alcances (scopes) sugeridos**:
  - `backend`, `edge`, `infra`, `frontend`, `firmware`, `docs`, `repo`.

### 4.2 Estrategia de Ramas
- Rama principal estable: `main`.
- Ramas de desarrollo de funcionalidades: `feature/<nombre-de-funcionalidad>`.
- Ramas de corrección: `fix/<nombre-del-bug>`.

---

## 5. Estándares y Convenciones de Código

### 5.1 Backend (Java / Spring Boot)
- **Paquete base**: `ar.edu.utn.frsf.tanques`
- **Subpaquetes estándar**:
  - `ar.edu.utn.frsf.tanques.auth`: Controladores, filtros JWT, servicios de autenticación y seguridad.
  - `ar.edu.utn.frsf.tanques.controller`: Endpoints REST (`/api/*`).
  - `ar.edu.utn.frsf.tanques.domain`: Entidades JPA, modelos del dominio.
  - `ar.edu.utn.frsf.tanques.dto`: Objetos de transferencia de datos de entrada/salida.
  - `ar.edu.utn.frsf.tanques.gateway`: Interfaces de actuadores (`ActuatorGateway`) y sus implementaciones (`MockActuatorGateway`, `BridgeActuatorGateway`).
  - `ar.edu.utn.frsf.tanques.telemetry`: Proveedores de telemetría (`TelemetryProvider`, `MockTelemetryProvider`, `InfluxTelemetryProvider`).
  - `ar.edu.utn.frsf.tanques.audit`: Entidades y servicios de registro de auditoría de comandos.
  - `ar.edu.utn.frsf.tanques.config`: Clases de configuración (@Configuration, OpenAPI, Seguridad, CORS).
  - `ar.edu.utn.frsf.tanques.exception`: Manejador global `@ControllerAdvice` y excepciones de negocio (`InterlockViolationException`, `BridgeUnavailableException`, etc.).
- **Manejo de Errores**: Códigos HTTP semánticos:
  - `401 Unauthorized`: Falta de token o credenciales incorrectas.
  - `403 Forbidden`: Usuario sin rol suficiente (ej. `ALUMNO` intentando accionar bomba o consultar auditoría).
  - `404 Not Found`: Actuador inexistente.
  - `409 Conflict`: Comando rechazado por interlock de seguridad (incluyendo en el cuerpo el `reason` de la falla).
  - `503 Service Unavailable`: Canal de control hacia el bridge no disponible (`reason: "bridge_unavailable"`).

### 5.2 Edge (Python)
- Python 3.10+.
- Cumplimiento de **PEP 8** y anotaciones de tipo (*type hints*).
- Manejo limpio de señales (`SIGINT`, `SIGTERM`) para cierre ordenado.
- En comunicación serial (`pyserial`): **siempre** deshabilitar DTR y RTS (`dtr=False`, `rts=False`) antes de abrir el puerto para evitar reiniciar el ESP32.

### 5.3 Frontend (React / TypeScript - Fase 3)
- Vite + React 18+ + TypeScript en modo estricto.
- Centralización de contratos de telemetría y comandos en `src/types/telemetry.ts`.
- Manejo de estado remoto con TanStack Query (polling configurable mediante `refetchInterval`). Sin WebSockets.
- Persistencia de JWT en memoria con respaldo en `sessionStorage`.

---

## 6. Procedimiento de Trabajo por Fases

El proyecto avanza estrictamente por fases según lo estipulado:
- **Fase 0**: Reglas del repo, contratos y documentación base.
- **Fase 1**: Simulador en Python (`edge/simulator.py`), bridge a InfluxDB (`edge/bridge.py`), Docker Compose (InfluxDB 2.x, Grafana, Nginx) y provisioning de dashboards.
- **Fase 2**: Backend Spring Boot 3.5.x, seguridad JWT, endpoints REST, auditoría H2, gateways y tests unitarios/integración.
- **Fase 3**: Frontend React SPA con Vite, TypeScript, vistas de monitoreo y panel de control por roles.

Al completar cada fase:
1. Asegurar que las pruebas y verificaciones manuales indicadas se cumplan.
2. Realizar los commits correspondientes según Conventional Commits.
3. **Regla Permanente de Mantenimiento Documental**: Actualizar obligatoriamente `CHANGELOG.md` y, si cambió algo de arquitectura, comandos o pendientes, `README.md` y `AGENTS.md`, en el mismo PR/rama y bajo un commit `docs(repo): ...`.
4. Detenerse (*FRENAR*), presentar un resumen ejecutivo de lo construido y esperar la confirmación explícita del usuario para continuar.

### 6.1 Regla Permanente de Mantenimiento Documental
> **REGLA PERMANENTE (CUMPLIMIENTO ESTRICTO):**  
> Al cerrar cada fase o fix relevante, actualizá `CHANGELOG.md` y, si cambió algo de arquitectura, comandos o pendientes, `README.md` y `AGENTS.md`, en el mismo PR/rama y con commit `docs(repo): ...`.

---

## 7. Pendientes Conocidos y Próximos Pasos

1. **Canal real de comandos backend $\to$ bridge $\to$ ESP32**:
   Hoy `BridgeActuatorGateway` en prod devuelve HTTP `503 Service Unavailable` (`bridge_unavailable`) porque `edge/bridge.py` actualmente solo implementa el canal de ingesta unidireccional (Serial $\to$ InfluxDB). Debe construirse un listener local de comandos (ej. HTTP REST local en `bridge.py` o socket IPC) para que el bridge despache la trama serial al ESP32 y retorne el `ack` correspondiente.
2. **Registro de auditoría no incluye `target`**:
   Verificar y garantizar la exposición y consumo homogéneo del campo `target` en todas las interfaces de auditoría y en las vistas del frontend.
3. **Calibración del interlock con el hardware físico real**:
   La apertura manual de la llave de interconexión Tanque A $\to$ Tanque B altera la tasa de descarga por gravedad y la altura máxima acumulada en B. En la puesta en marcha con hardware se debe calibrar el umbral y evaluar un interlock de corte por volumen total combinado ($V_A + V_B$). El interlock definitivo de seguridad de última barrera reside obligatoriamente en el firmware del ESP32.
4. **Divergencia de telemetría en desarrollo vs producción**:
   En perfil `dev` el backend genera telemetría simulada con `MockTelemetryProvider` en memoria, mientras que Grafana lee los puntos generados por `edge/bridge.py` + `edge/simulator.py` en InfluxDB. Ambas fuentes se unifican de forma transparente en perfil `prod`, donde tanto backend como Grafana consumen InfluxDB 2.x.
