# Especificación de la API REST del Backend (Spring Boot 3.5.x)

**Proyecto**: Kit Didáctico de Tanques Interconectados (UTN FRSF / GITDA)  
**Compatibilidad**: Obsidian Markdown / CommonMark  
**Documentación OpenAPI / Swagger**: `/swagger-ui.html` y `/v3/api-docs`

---

## 1. Arquitectura y Seguridad de la API

La API REST del backend está construida sobre **Java 21** y **Spring Boot 3.5.x** con seguridad stateless mediante **JSON Web Tokens (JWT)** firmados con algoritmo HMAC-SHA256 (`jjwt 0.12.6`).

### 1.1 Esquema de Autenticación
- Todos los endpoints bajo `/api/**` requieren autenticación, excepto `/api/auth/login`.
- El cliente debe enviar el token en la cabecera HTTP:
  ```http
  Authorization: Bearer <token_jwt>
  ```
- **Secreto JWT**: En desarrollo (`dev`) utiliza una clave por defecto de 32+ caracteres. En producción (`prod`), el secreto **debe** provenir obligatoriamente de la variable de entorno `JWT_SECRET` (sin valor por defecto y con longitud mínima de 32 caracteres / 256 bits).

### 1.2 Roles y Matriz de Control de Acceso (RBAC)

| Endpoint | Método | Rol Permitido | Propósito |
| :--- | :---: | :---: | :--- |
| `/api/auth/login` | `POST` | Público | Autenticación y obtención de JWT |
| `/api/me` | `GET` | `ALUMNO`, `DOCENTE` | Consulta del perfil de usuario activo |
| `/api/telemetry/latest` | `GET` | `ALUMNO`, `DOCENTE` | Lectura de última trama de telemetría normalizada |
| `/api/actuators` | `GET` | `ALUMNO`, `DOCENTE` | Consulta del estado actual de actuadores (`pump`, etc.) |
| `/api/actuators/{name}` | `POST` | **`DOCENTE` únicamente** | Envío de comando de control con validación de interlocks |
| `/api/audit` | `GET` | **`DOCENTE` únicamente** | Registro histórico de auditoría de comandos |
| `/swagger-ui.html` | `GET` | Público | Explorador interactivo OpenAPI 3 (Swagger UI) |
| `/h2-console/**` | `GET/POST` | Público (solo perfil `dev`) | Consola web de administración de base de datos H2 |

### 1.3 Códigos de Respuesta Semánticos

- `200 OK`: Solicitud procesada exitosamente.
- `400 Bad Request`: Parámetros o cuerpo JSON inválidos o faltantes.
- `401 Unauthorized`: Token faltante, expirado, inválido o credenciales incorrectas.
- `403 Forbidden`: Usuario autenticado pero sin rol suficiente (ej. `ALUMNO` intentando accionar `/api/actuators/pump`).
- `404 Not Found`: Recurso no encontrado (ej. actuador inexistente).
- `409 Conflict`: Comando rechazado por **interlock de seguridad físico/lógico** (ej. sobrellenado `overflow_a` / `overflow_b`).

---

## 2. Detalle de Endpoints

### 2.1 Autenticación

#### `POST /api/auth/login`
Autentica al usuario contra la base de datos H2.

**Request Body**:
```json
{
  "username": "docente",
  "password": "docente123"
}
```

*Credenciales sembradas por defecto en arranque*:
- Docente: `username: "docente"`, `password: "docente123"`
- Alumno: `username: "alumno"`, `password: "alumno123"`

**Response (200 OK)**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9...",
  "username": "docente",
  "role": "DOCENTE"
}
```

**Response (401 Unauthorized)**:
```json
{
  "timestamp": "2026-10-15T04:45:00.000Z",
  "status": 401,
  "error": "Unauthorized",
  "message": "Credenciales inválidas"
}
```

---

#### `GET /api/me`
Retorna los datos del usuario extraídos del token JWT activo.

**Headers**:
```http
Authorization: Bearer <token_jwt>
```

**Response (200 OK)**:
```json
{
  "username": "docente",
  "role": "DOCENTE"
}
```

---

### 2.2 Telemetría

#### `GET /api/telemetry/latest`
Obtiene la última trama normalizada de telemetría física. En perfil `dev` proviene del proveedor simulado sincronizado en memoria (`MockTelemetryProvider`); en perfil `prod` consulta InfluxDB 2.x mediante la librería `influxdb-client-java`.

**Response (200 OK)**:
```json
{
  "timestamp": 1740000000,
  "tanque_a": {
    "nivel": 45.2,
    "volumen": 3.2,
    "temperatura": 24.1,
    "sensor_fault": false
  },
  "tanque_b": {
    "nivel": 30.1,
    "volumen": 2.1,
    "temperatura": 23.8,
    "sensor_fault": false
  },
  "actuadores": {
    "pump": true
  },
  "interlocks": {
    "overflow_a": false,
    "overflow_b": false
  }
}
```

---

### 2.3 Actuadores y Control

#### `GET /api/actuators`
Retorna el mapa extensible del estado de todos los actuadores registrados.

**Response (200 OK)**:
```json
{
  "pump": false
}
```

---

#### `POST /api/actuators/{name}`
Ejecuta una acción sobre un actuador. Requiere rol `DOCENTE`.
Verifica primero si el actuador existe; si existe, somete la acción a las reglas de interlocks físicos. Toda acción (exitosa o rechazada) se registra en la tabla de auditoría H2.

**Path Variable**:
- `name`: Nombre del actuador (ej. `pump`).

**Request Body**:
```json
{
  "value": true
}
```

**Response (200 OK - Comando Aceptado)**:
```json
{
  "target": "pump",
  "value": true,
  "status": "SUCCESS",
  "reason": null
}
```

**Response (409 Conflict - Rechazo por Interlock de Seguridad)**:
Si el nivel del tanque A o B excede el umbral del 95%:
```json
{
  "target": "pump",
  "value": true,
  "status": "REJECTED_BY_INTERLOCK",
  "reason": "overflow_a"
}
```

**Response (403 Forbidden - Usuario no autorizado)**:
Si un usuario con rol `ALUMNO` intenta ejecutar el comando:
```json
{
  "timestamp": "2026-10-15T04:45:00.000Z",
  "status": 403,
  "error": "Forbidden",
  "message": "Acceso denegado: no posee privilegios suficientes"
}
```

---

### 2.4 Auditoría

#### `GET /api/audit`
Obtiene los últimos eventos registrados de comandos sobre actuadores, ordenados cronológicamente descendente. Requiere rol `DOCENTE`.

**Response (200 OK)**:
```json
[
  {
    "id": 1,
    "timestamp": "2026-10-15T01:42:31.390Z",
    "username": "docente",
    "target": "pump",
    "value": true,
    "status": "SUCCESS",
    "reason": null
  },
  {
    "id": 2,
    "timestamp": "2026-10-15T01:42:31.240Z",
    "username": "docente",
    "target": "pump",
    "value": true,
    "status": "REJECTED_BY_INTERLOCK",
    "reason": "overflow_a"
  }
]
```

---

## 3. Persistencia H2 en Disco

La base de datos H2 se persiste en el directorio local `./data/` de acuerdo con las especificaciones del proyecto:
- URL de conexión: `jdbc:h2:file:./data/tanquesdb;DB_CLOSE_DELAY=-1;AUTO_SERVER=TRUE`
- Los archivos generados (`tanquesdb.mv.db`, `tanquesdb.trace.db`, etc.) están excluidos del repositorio mediante `.gitignore`.
- La persistencia asegura que los usuarios y el historial de comandos auditados sobrevivan a reinicios del proceso backend.

---

## 4. Ejecución del Backend

### Perfil Desarrollo (`dev`)
No requiere Docker, ni ESP32 ni InfluxDB. Corre completamente autónomo con mocks sincronizados:
```bash
cd backend
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```
- API Base: `http://localhost:8080`
- Swagger UI: `http://localhost:8080/swagger-ui.html`
- OpenAPI JSON: `http://localhost:8080/v3/api-docs`
- Consola H2: `http://localhost:8080/h2-console` (JDBC URL: `jdbc:h2:file:./data/tanquesdb`)

### Perfil Producción (`prod`)
Se ejecuta en el borde (Raspberry Pi) conectado con InfluxDB 2.x y el Bridge serial:
```bash
export JWT_SECRET="clave-super-secreta-de-produccion-minimo-32-caracteres-utn"
mvn spring-boot:run -Dspring-boot.run.profiles=prod
```
