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
4. **Backend**:
   - Java 21, Spring Boot 3.x, Maven.
   - Seguridad con JWT stateless. Roles: `DOCENTE` (permisos de control de actuadores y auditoría) y `ALUMNO` (solo lectura).
   - Persistencia de usuarios y eventos de auditoría en base de datos H2 (modo archivo).
   - Documentación viva de endpoints mediante OpenAPI 3 (`springdoc-openapi`) expuesta en `/swagger-ui.html`.
   - Aislamiento de perfiles: en perfil `dev` el backend corre localmente **sin Docker y sin ESP32** (con mocks en memoria).
5. **Timestamping**:
   El ESP32 no tiene RTC. La Raspberry Pi asigna el timestamp oficial al momento de recibir la trama JSON e insertarla en InfluxDB.
6. **Geometría Configurable**:
   El área transversal de cada tanque (cilindros de distintos diámetros) y los factores de conversión deben residir en archivos de configuración (`edge/config.yaml` / `application.yml`), nunca hardcodeados.
7. **Diseño Extensible de Actuadores**:
   Actualmente el único actuador físico es la bomba (`pump`). El sistema debe modelar el estado de actuadores como un mapa extensible (`Map<String, Boolean>`) y desacoplar la validación de targets para que agregar nuevos actuadores futuros no requiera modificar la arquitectura.

---

## 3. Delimitación de Alcance (Scope Boundaries)

- **FUERA DE ALCANCE (ESTRICTO)**: Placas Peltier, celdas de efecto termoeléctrico y cualquier mecanismo de control térmico activo. La temperatura registrada en los tanques es exclusivamente de **monitoreo**. No modelar, documentar, simular ni implementar nada relacionado con Peltier.
- **Válvulas**: Las llaves de paso entre los tanques y hacia el reservorio son manuales. No existe sensado ni control de válvulas en el protocolo.
- **Plataforma de despliegue**: Raspberry Pi (local). No se utilizan servicios en la nube (AWS, Azure, etc.).

---

## 4. Convenciones de Git y Control de Versiones

### 4.1 Conventional Commits
Cada commit debe respetar la especificación [Conventional Commits](https://www.conventionalcommits.org/):

```
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
  - `ar.edu.utn.frsf.tanques.exception`: Manejador global `@ControllerAdvice` y excepciones de negocio (`InterlockViolationException`, etc.).
- **Manejo de Errores**: Códigos HTTP semánticos:
  - `401 Unauthorized`: Falta de token o credenciales incorrectas.
  - `403 Forbidden`: Usuario sin rol suficiente (ej. ALUMNO intentando accionar bomba).
  - `409 Conflict`: Comando rechazado por interlock de seguridad (incluyendo en el cuerpo el `reason` de la falla).

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
- **Fase 2**: Backend Spring Boot 3.x, seguridad JWT, endpoints REST, auditoría H2, gateways y tests unitarios/integración.
- **Fase 3**: Frontend React SPA con Vite, TypeScript, vistas de monitoreo y panel de control por roles.

Al completar cada fase:
1. Asegurar que las pruebas y verificaciones manuales indicadas se cumplan.
2. Realizar los commits correspondientes según Conventional Commits.
3. Detenerse (*FRENAR*), presentar un resumen ejecutivo de lo construido y esperar la confirmación explícita del usuario para continuar.
