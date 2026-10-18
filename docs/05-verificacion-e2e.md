# Guía de Verificación Integral de Punta a Punta (E2E) en Producción

Esta guía describe el procedimiento de verificación completa de punta a punta (*End-to-End*) del sistema didáctico de tanques en perfil de producción (`prod`), validando la interacción de la infraestructura Docker, el bridge de telemetría y comandos, el backend Spring Boot con autenticación JWT y auditoría, el broker MQTT Mosquitto, y la interfaz web (SPA).

---

## 1. Consideraciones y Notas Previas Críticas

Antes de comenzar la ejecución de comandos, tener en cuenta las siguientes lecciones aprendidas:

1. **Variables de entorno por terminal (`$env:`)**:  
   En PowerShell, las variables asignadas con `$env:VARIABLE = "valor"` tienen alcance **únicamente dentro de la sesión de terminal actual**. Si se abre una nueva pestaña o ventana, se deben volver a definir las variables requeridas para ese proceso.

2. **Marcadores ilustrativos (`<TU_CLAVE_...>`)**:  
   En los comandos de ejemplo se utilizan marcadores como `<TU_CLAVE_MOSQUITTO>`, `<TU_JWT_SECRET_MIN_32_CHARS>`, `<TU_PASSWORD_DOCENTE>`, `<TU_PASSWORD_ALUMNO>` e `<INFLUX_TOKEN>`. **No son valores literales ni deben ejecutarse con los signos `<` y `>`**. Deben sustituirse por las claves reales y seguras generadas para el entorno de producción.

3. **Quoting de parámetros Maven en PowerShell 5.1**:  
   En PowerShell 5.1 (estándar en Windows), los argumentos con puntos y guiones pueden ser interpretados de manera incorrecta. Debe utilizarse siempre entre comillas dobles:  
   `mvn spring-boot:run "-Dspring-boot.run.profiles=prod"`

4. **Persistencia de usuarios en H2 y resembrado**:  
   En perfil `prod`, la base de datos H2 persiste en disco en `./backend/data/tanquesdb.*`. La clase `DataInitializer` solo siembra los usuarios iniciales (`docente` y `alumno`) si la tabla de usuarios está vacía. Si se modifican las variables `$env:DOCENTE_PASSWORD` o `$env:ALUMNO_PASSWORD`, **es obligatorio detener el backend y eliminar la carpeta `backend/data/`** para que las contraseñas se reencripten con BCrypt al reiniciar.

5. **Sincronización de contraseñas en Mosquitto**:  
   Mosquitto no lee directamente las variables de entorno en tiempo de ejecución; valida credenciales contra el archivo `infra/mosquitto/passwords`. Si se modifica la contraseña de MQTT en `infra/.env` o `$env:MQTT_PASSWORD`, se debe regenerar el archivo de contraseñas dentro del contenedor:  
   `docker compose exec mosquitto mosquitto_passwd -b /mosquitto/config/passwords tanques <TU_CLAVE_MOSQUITTO>`  
   y reiniciar el servicio con `docker compose restart mosquitto`.

---

## 2. Esquema de las 5 Terminales

Para una verificación integral y desacoplada, se recomienda operar con 5 terminales abiertas simultáneamente:

| Terminal | Rol / Componente | Directorio de Trabajo | Propósito |
| :--- | :--- | :--- | :--- |
| **T1** | Infraestructura Docker | `infra/` | Contenedores InfluxDB, Grafana, Mosquitto, Nginx |
| **T2** | Bridge / Simulador Edge | `edge/` | Pipeline de telemetría y control serial |
| **T3** | Backend Spring Boot (`prod`) | `backend/` | API REST, seguridad JWT, gateway Paho MQTT, H2 |
| **T4** | Monitor MQTT (Mosquitto Sub) | Raíz del proyecto | Inspección en tiempo real de `tanques/cmd` y `tanques/ack` |
| **T5** | Cliente de Pruebas REST | Raíz del proyecto | Comandos curl / PowerShell, autenticación y auditoría |

---

## 3. Procedimiento Paso a Paso

### Terminal 1 (T1) — Infraestructura Docker

1. Navegar al directorio de infraestructura y configurar el archivo `.env`:
   ```powershell
   cd infra
   # Asegurar que .env contenga las credenciales productivas de Mosquitto e InfluxDB
   ```

2. Levantar los servicios en segundo plano:
   ```powershell
   docker compose up -d
   ```

3. Verificar que los 4 contenedores estén en ejecución (`Up`):
   ```powershell
   docker compose ps
   ```
   Deben reportar estado saludable:
   - `infra-mosquitto-1` (puerto `1883`)
   - `infra-influxdb-1` (puerto `8086`)
   - `infra-grafana-1` (puerto `3000`)
   - `infra-nginx-1` (puerto `80`)

---

### Terminal 2 (T2) — Bridge y Simulador Edge

El bridge procesa la telemetría del equipo físico (o simulador de hardware) y escucha comandos seriales para relay bidireccional.

1. Navegar a `edge/`:
   ```powershell
   cd edge
   ```
   *(Nota: Si usás entorno virtual `.venv`, activalo con `.\.venv\Scripts\Activate.ps1`. Si no lo creaste previamente, podés crearlo con `python -m venv .venv` y `pip install -r requirements.txt`, o ejecutar directamente con tu Python global si ya tiene las dependencias instaladas)*.

2. Configurar el token de InfluxDB y la clave de Mosquitto en las variables de sesión:
   ```powershell
   $env:INFLUX_TOKEN = "<INFLUX_TOKEN>"
   $env:MQTT_PASSWORD = "<TU_CLAVE_MOSQUITTO>"
   ```

3. Iniciar el bridge con simulación interna activa:
   ```powershell
   python bridge.py --source sim
   ```
   *(O para acelerar el llenado y verificar interlocks: `python bridge.py --source sim --pump-on --sim-speed 3.0`)*.

   *Salida esperada*: confirmación de conexión exitosa a Mosquitto (`Conectado al broker MQTT`), suscripción a `tanques/cmd`, e inserción periódica de puntos de telemetría en InfluxDB.

---

### Terminal 3 (T3) — Backend Spring Boot en Perfil Producción

1. Navegar a `backend/`:
   ```powershell
   cd backend
   ```

2. Definir las variables de entorno de producción obligatorias:
   ```powershell
   $env:JWT_SECRET       = "<TU_JWT_SECRET_MIN_32_CHARS>"
   $env:DOCENTE_PASSWORD = "<TU_PASSWORD_DOCENTE>"
   $env:ALUMNO_PASSWORD  = "<TU_PASSWORD_ALUMNO>"
   $env:MQTT_PASSWORD    = "<TU_CLAVE_MOSQUITTO>"
   $env:INFLUX_URL       = "http://localhost:8086"
   $env:INFLUX_TOKEN     = "<INFLUX_TOKEN>"
   ```

3. Iniciar la aplicación en perfil `prod`:
   ```powershell
   mvn spring-boot:run "-Dspring-boot.run.profiles=prod"
   ```
   *Salida esperada*:
   - Inicialización de persistencia H2 en disco.
   - Creación de usuarios semilla `docente` y `alumno`.
   - Conexión del cliente Paho MQTT a `localhost:1883` y suscripción al tópico `tanques/ack` con QoS 1.
   - Arranque del servidor HTTP en el puerto `8080`.

---

### Terminal 4 (T4) — Monitor de Tópicos MQTT

Permite auditar el tráfico del bus de control sin interferir en el pipeline:

```powershell
cd infra
docker compose exec mosquitto mosquitto_sub -t "tanques/#" -u tanques -P "<TU_CLAVE_MOSQUITTO>" -v
```

*Salida esperada*: se observará cada publicación entrante en `tanques/cmd` y la respuesta inmediata emitida por el bridge en `tanques/ack`.

---

### Terminal 5 (T5) — Verificación de Endpoints y Casos de Prueba

#### A. Autenticación y Obtención de Tokens JWT

1. **Login como DOCENTE**:
   ```powershell
   $docenteLogin = Invoke-RestMethod -Uri "http://localhost:8080/api/auth/login" `
     -Method Post -ContentType "application/json" `
     -Body '{"username":"docente","password":"<TU_PASSWORD_DOCENTE>"}'

   $tokenDocente = $docenteLogin.token
   $headersDocente = @{ Authorization = "Bearer $tokenDocente" }
   ```

2. **Login como ALUMNO**:
   ```powershell
   $alumnoLogin = Invoke-RestMethod -Uri "http://localhost:8080/api/auth/login" `
     -Method Post -ContentType "application/json" `
     -Body '{"username":"alumno","password":"<TU_PASSWORD_ALUMNO>"}'

   $tokenAlumno = $alumnoLogin.token
   $headersAlumno = @{ Authorization = "Bearer $tokenAlumno" }
   ```

---

#### B. Consulta de Telemetría y Estado de Actuadores

1. **Consultar última telemetría**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8080/api/telemetry/latest" -Headers $headersDocente
   ```

2. **Consultar estado actual de actuadores**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8080/api/actuators" -Headers $headersDocente
   ```
   *Respuesta esperada* (telemetría reciente):
   ```json
   {
     "pump": false
   }
   ```
   *(Si no hay telemetría reciente en los últimos 5 segundos, responde `{"pump": null}`, indicando estado desconocido)*.

---

#### C. Caso 1: Comando Feliz (Encendido y Apagado)

1. **Encender la bomba (DOCENTE)**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8080/api/actuators/pump" `
     -Method Post -Headers $headersDocente -ContentType "application/json" `
     -Body '{"value": true}'
   ```
   *Respuesta real de la API (HTTP 200 OK)*:
   ```json
   {
     "ack": "c_3f8a12bc",
     "ok": true,
     "reason": null,
     "target": "pump",
     "value": true,
     "timestamp": 1729185200123
   }
   ```
   *En T4 se observará*:
   ```text
   tanques/cmd {"id":"c_3f8a12bc","cmd":"set","target":"pump","value":true,"ts":1729185200100}
   tanques/ack {"ack":"c_3f8a12bc","ok":true,"reason":null,"target":"pump","value":true,"timestamp":1729185200123}
   ```

2. **Apagar la bomba (DOCENTE)**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8080/api/actuators/pump" `
     -Method Post -Headers $headersDocente -ContentType "application/json" `
     -Body '{"value": false}'
   ```
   *Respuesta real de la API (HTTP 200 OK)*:
   ```json
   {
     "ack": "c_7b4c91ea",
     "ok": true,
     "reason": null,
     "target": "pump",
     "value": false,
     "timestamp": 1729185215456
   }
   ```

---

#### D. Caso 2: Interlock de Seguridad de Sobrellenado (HTTP 409 Conflict)

Cuando el nivel de agua en Tanque A o Tanque B supera el umbral configurado (85.0 %), cualquier intento de encendido es abortado por seguridad.

1. **Envío de comando con interlock activo**:
   ```powershell
   try {
     Invoke-RestMethod -Uri "http://localhost:8080/api/actuators/pump" `
       -Method Post -Headers $headersDocente -ContentType "application/json" `
       -Body '{"value": true}'
   } catch {
     $stream = $_.Exception.Response.GetResponseStream()
     $reader = New-Object System.IO.StreamReader($stream)
     $reader.ReadToEnd()
   }
   ```
   *Respuesta real de la API (HTTP 409 Conflict)*:
   ```json
   {
     "ack": "c_9e12fa33",
     "ok": false,
     "reason": "overflow_a",
     "target": "pump",
     "value": true,
     "timestamp": 1729185240789
   }
   ```

---

#### E. Caso 3: Rechazo por Telemetría Obsoleta / Influx Caído (HTTP 409 Conflict)

Si la telemetría no se renueva por más de 5 segundos (por ejemplo, si el bridge o InfluxDB dejan de emitir tramas):
- Un intento de encendido (`value: true`) es rechazado de inmediato antes de publicar a MQTT:
  ```json
  {
    "ack": null,
    "ok": false,
    "reason": "telemetry_stale",
    "target": "pump",
    "value": true,
    "timestamp": 1729185260100
  }
  ```
- Un comando de apagado (`value: false`) **permanece siempre permitido** por seguridad física y se transmite al bus MQTT.

---

#### F. Caso 4: Control de Acceso por Roles (ALUMNO no autorizado - HTTP 403)

Si un usuario con rol `ALUMNO` intenta enviar una orden de control de actuadores:
```powershell
try {
  Invoke-RestMethod -Uri "http://localhost:8080/api/actuators/pump" `
    -Method Post -Headers $headersAlumno -ContentType "application/json" `
    -Body '{"value": false}'
} catch {
  $_.Exception.Response.StatusCode.value__
}
```
*Respuesta esperada*: `403` (Forbidden).

---

#### G. Caso 5: Resiliencia ante Caída del Broker Mosquitto (HTTP 503)

1. Detener el broker Mosquitto desde `infra/`:
   ```powershell
   docker compose stop mosquitto
   ```

2. Intentar enviar un comando desde T5:
   ```powershell
   try {
     Invoke-RestMethod -Uri "http://localhost:8080/api/actuators/pump" `
       -Method Post -Headers $headersDocente -ContentType "application/json" `
       -Body '{"value": false}'
   } catch {
     $stream = $_.Exception.Response.GetResponseStream()
     $reader = New-Object System.IO.StreamReader($stream)
     $reader.ReadToEnd()
   }
   ```
   *Respuesta esperada (HTTP 503 Service Unavailable)*:
   ```json
   {
     "error": "bridge_unavailable",
     "message": "Control no disponible: sin conexión con el broker MQTT"
   }
   ```

3. Volver a iniciar Mosquitto:
   ```powershell
   docker compose start mosquitto
   ```
   *Comportamiento esperado*: En T3, el hilo daemon de fondo reconectará automáticamente y se resuscribirá a `tanques/ack`. Al reintentar el comando tras 5-10 segundos, responderá `200 OK` sin haber requerido reiniciar el backend.

---

#### H. Caso 6: Auditoría de Comandos

La auditoría almacena todos los intentos de comando, exitosos o fallidos.

1. **Consultar el registro de auditoría (DOCENTE)**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8080/api/audit" -Headers $headersDocente | Format-Table
   ```
   *Estructura real de los registros JSON*:
   ```json
   [
     {
       "id": 1,
       "username": "docente",
       "target": "pump",
       "requestedValue": true,
       "ok": true,
       "reason": null,
       "timestamp": "2026-10-17T17:25:00.123Z"
     },
     {
       "id": 2,
       "username": "docente",
       "target": "pump",
       "requestedValue": true,
       "ok": false,
       "reason": "overflow_a",
       "timestamp": "2026-10-17T17:25:40.789Z"
     },
     {
       "id": 3,
       "username": "docente",
       "target": "pump",
       "requestedValue": true,
       "ok": false,
       "reason": "telemetry_stale",
       "timestamp": "2026-10-17T17:26:00.100Z"
     }
   ]
   ```

---

### 4. Verificación de la SPA y Grafana

1. Acceder desde el navegador web a:
   - `http://localhost/`: Interfaz web (SPA React).
   - Iniciar sesión como `docente` o `alumno`.
   - Verificar que la etiqueta de estado indique **"Equipo Conectado"** (verde).
   - Comprobar que los paneles embebidos de Grafana en el iframe muestren los niveles, caudales y temperaturas con formato decimal correcto (`0.1%`, `0.00 L/min`, `23.5 °C`).
   - Para el rol `DOCENTE`: probar el accionamiento de la bomba desde el panel interactivo.
   - Para el rol `ALUMNO`: verificar que los botones de control y la solapa de auditoría permanezcan ocultos o deshabilitados.
