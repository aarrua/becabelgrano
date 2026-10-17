# Flujo de Comandos y Mecanismos de Seguridad (Interlocks)

**Proyecto**: Kit Didáctico de Tanques Interconectados (UTN FRSF / GITDA)  
**Compatibilidad**: Obsidian Markdown / CommonMark

---

## 1. Filosofía de Seguridad y Defensa en Profundidad

En aplicaciones de Industria 4.0 y control de procesos físicos, la seguridad de las personas y del equipo (*interlocks* y parada segura) prima sobre cualquier orden de operación.

El sistema implementa **cuatro capas de defensa en profundidad**:

1. **Capa 1 (Frontend)**: La interfaz gráfica adapta sus controles dinámicamente según el rol reportado por el token JWT. Los usuarios con rol `ALUMNO` tienen una vista exclusivamente de monitoreo; el panel de control de actuadores no se renderiza.
2. **Capa 2 (Control de Acceso en Backend)**: Los endpoints de mutación (`POST /api/actuators/{name}`) están custodiados por anotaciones `@PreAuthorize("hasRole('DOCENTE')")`. Cualquier solicitud de un usuario no docente es rechazada de inmediato con `403 Forbidden`.
3. **Capa 3 (Validación en ActuatorGateway)**: El backend valida que el comando cumpla con las reglas del dominio y con el estado de seguridad antes de despacharlo hacia el bridge.
4. **Capa 4 (Interlock en Hardware / Firmware)**: El Arduino Uno (y el simulador) contiene la lógica de corte duro autónomo. Si el nivel en cualquiera de los tanques supera el 95% (`overflow_a` u `overflow_b`), la bomba se detiene automáticamente por hardware y cualquier intento de encendido es rechazado con código de fallo específico (`reason: "overflow_a"`).

---

## 2. Diagrama de Secuencia de Comandos

El siguiente diagrama detalla los tres flujos fundamentales: ejecución exitosa, rechazo por interlock físico y bloqueo por autorización.

```mermaid
sequenceDiagram
    autonumber
    actor Docente as Docente
    actor Alumno as Alumno
    participant Front as Frontend (React)
    participant Nginx as Nginx (:80)
    participant Spring as Spring Boot (:8080)
    participant H2 as H2 DB (Auditoría)
    participant Gateway as ActuatorGateway
    participant Bridge as Bridge Python
    participant Arduino as Arduino Uno (Firmware)

    %% ========================================================
    %% CASO 1: COMANDO EXITOSO
    %% ========================================================
    rect rgb(235, 248, 235)
        note over Docente, Arduino: CASO 1: Ejecución Exitosa de Comando (Bomba ON)
        Docente->>Front: Click "Encender Bomba"
        Front->>Nginx: POST /api/actuators/pump { "value": true }<br/>[Header: Authorization Bearer JWT_DOCENTE]
        Nginx->>Spring: Proxy /api/actuators/pump
        Spring->>Spring: Valida JWT y Rol DOCENTE (OK)
        Spring->>Gateway: executeCommand("pump", true)
        Gateway->>Bridge: JSON {"id": "c101", "cmd": "set", "target": "pump", "value": true}
        Bridge->>Arduino: Serial JSON {"id":"c101","cmd":"set","target":"pump","value":true}\n
        Arduino->>Arduino: Verifica nivel tanques (< 95%)<br/>Acciona relé bomba (ON)
        Arduino-->>Bridge: Serial JSON {"ack":"c101","ok":true}\n
        Bridge-->>Gateway: AckCommand { ack: "c101", ok: true }
        Gateway-->>Spring: CommandResult (SUCCESS)
        Spring->>H2: Guardar auditoría (Docente, "pump", true, SUCCESS, timestamp)
        Spring-->>Nginx: 200 OK {"target":"pump","value":true,"status":"SUCCESS"}
        Nginx-->>Front: 200 OK
        Front-->>Docente: Muestra estado Bomba: ENCENDIDA (Verde)
    end

    %% ========================================================
    %% CASO 2: RECHAZO POR INTERLOCK (SEGURIDAD FÍSICA)
    %% ========================================================
    rect rgb(255, 238, 238)
        note over Docente, Arduino: CASO 2: Rechazo Seguro por Interlock (Nivel Tanque A > 95%)
        Docente->>Front: Click "Encender Bomba"
        Front->>Nginx: POST /api/actuators/pump { "value": true }<br/>[Header: Authorization Bearer JWT_DOCENTE]
        Nginx->>Spring: Proxy /api/actuators/pump
        Spring->>Spring: Valida JWT y Rol DOCENTE (OK)
        Spring->>Gateway: executeCommand("pump", true)
        Gateway->>Bridge: JSON {"id": "c102", "cmd": "set", "target": "pump", "value": true}
        Bridge->>Arduino: Serial JSON {"id":"c102","cmd":"set","target":"pump","value":true}\n
        Arduino->>Arduino: EVALUACIÓN INTERLOCK: Nivel A = 96.2% (> 95%)<br/>¡Bomba se mantiene apagada!
        Arduino-->>Bridge: Serial JSON {"ack":"c102","ok":false,"reason":"overflow_a"}\n
        Bridge-->>Gateway: AckCommand { ack: "c102", ok: false, reason: "overflow_a" }
        Gateway-->>Spring: Lanza InterlockViolationException("overflow_a")
        Spring->>H2: Guardar auditoría (Docente, "pump", true, REJECTED, reason="overflow_a")
        Spring-->>Nginx: 409 Conflict {"error":"Interlock violation","reason":"overflow_a"}
        Nginx-->>Front: 409 Conflict
        Front-->>Docente: Alerta visual: "Comando rechazado: Sobrellenado activo en Tanque A"
    end

    %% ========================================================
    %% CASO 3: RECHAZO POR ROL (ALUMNO)
    %% ========================================================
    rect rgb(240, 240, 255)
        note over Alumno, Spring: CASO 3: Intento no autorizado por usuario ALUMNO
        Alumno->>Nginx: POST /api/actuators/pump { "value": true }<br/>[Header: Authorization Bearer JWT_ALUMNO]
        Nginx->>Spring: Proxy /api/actuators/pump
        Spring->>Spring: Spring Security evalúa @PreAuthorize("hasRole('DOCENTE')")<br/>Usuario solo posee rol ALUMNO
        Spring-->>Nginx: 403 Forbidden {"error":"Access Denied","message":"Permisos insuficientes"}
        Nginx-->>Alumno: 403 Forbidden
        note over Gateway, Arduino: La orden NUNCA llega al Gateway, Bridge ni Hardware
    end
```

---

## 3. Registro de Auditoría

Cada comando procesado por el backend genera un registro inmutable en la tabla de auditoría en H2, accesible mediante `GET /api/audit` únicamente para el rol `DOCENTE`:

| Campo | Tipo | Ejemplo | Descripción |
|---|---|---|---|
| `id` | Long | `42` | Clave primaria autoincremental. |
| `timestamp` | Instant / UTC | `2026-10-14T23:45:00Z` | Momento exacto de recepción de la orden. |
| `username` | String | `"docente"` | Nombre del usuario autenticado vía JWT. |
| `target` | String | `"pump"` | Actuador involucrado. |
| `command_value` | String | `"true"` | Valor solicitado por el usuario. |
| `result` | String | `"SUCCESS"` \| `"REJECTED"` | Resultado de la operación. |
| `reason` | String | `"overflow_a"` \| `null` | Causa de rechazo en caso de falla o interlock. |
