# Infraestructura Docker - Kit Didáctico de Tanques (UTN FRSF / GITDA)

Este directorio contiene la configuración y orquestación de los servicios base de infraestructura que se ejecutan como contenedores Docker para la plataforma en la Raspberry Pi / host local.

---

## 1. Servicios Orquestados (`docker-compose.yml`)

| Contenedor | Imagen y Versión | Puerto Expuesto | Rol |
|---|---|:---:|---|
| **`tanques-influxdb`** | `influxdb:2.7.10-alpine` | `8086` | Base de datos de series temporales (TSDB) para telemetría |
| **`tanques-grafana`** | `grafana/grafana-oss:11.2.0` | `3000` | Dashboards visuales de monitoreo (Viewer anónimo, embedding habilitado) |
| **`tanques-mosquitto`** | `eclipse-mosquitto:2.0.22` | `1883` | Broker MQTT para canal de comandos (`tanques/cmd`) y acks (`tanques/ack`) |
| **`tanques-nginx`** | `nginx:1.26.2-alpine` | `80` | Punto de entrada único HTTP (Reverse Proxy y servidor web de la SPA) |

---

## 2. Broker Mosquitto MQTT

### 2.1 Configuración de Seguridad y Red
- Mosquitto opera con **autenticación obligatoria por usuario y contraseña** (`allow_anonymous false`).
- Escucha en `0.0.0.0:1883`. Las contraseñas se almacenan hasheadas (PBKDF2-SHA512) en `infra/mosquitto/passwords`.
- **Aislamiento en Jornadas**: En demostraciones, jornadas o pruebas presenciales, el sistema debe desplegarse siempre sobre una **red propia aislada** (router Wi-Fi o hotspot portátil dedicado), **nunca sobre la red institucional**.

> **Seguridad**: El archivo `passwords` **nunca se commitea al repositorio** (ignorado por `.gitignore`). Debe ser generado en el entorno de despliegue mediante los scripts provistos.

### 2.2 Generación del Archivo de Contraseñas
Los scripts multiplataforma utilizan la propia imagen Docker de Mosquitto para evitar dependencias locales. **Validan estrictamente** que la contraseña no esté vacía ni contenga el valor de ejemplo por defecto (`cambiar-esta-clave`):

- **En Linux / macOS / Git Bash**:
  ```bash
  cd infra/mosquitto
  chmod +x init-passwords.sh
  ./init-passwords.sh tanques mi_password_segura
  ```

- **En Windows (PowerShell)**:
  ```powershell
  cd infra\mosquitto
  .\init-passwords.ps1 -Username tanques -Password mi_password_segura
  ```

Si no se pasan parámetros, el script lee `MQTT_USER` y `MQTT_PASSWORD` desde `infra/.env`. Si el valor es `cambiar-esta-clave` o está vacío, la ejecución se interrumpe con error para impedir arranques con credenciales inseguras.

### 2.3 Tópicos y QoS
El broker Mosquitto administra los tópicos del canal bidireccional de control entre el backend y el edge:
- **`tanques/cmd`**: El Backend Spring Boot publica órdenes de control de actuadores en formato JSON (especificado en `docs/01-contrato-datos.md`) con **QoS 1**.
- **`tanques/ack`**: El Bridge Python suscribe al hardware/simulador y publica la confirmación o rechazo del comando con **QoS 1**.

---

## 3. Nginx: Punto de Entrada Único y Proxies

El contenedor **Nginx** unifica el acceso en el puerto 80 (`http://localhost`):

1. **`/` (Frontend SPA)**:
   Sirve los estáticos compilados de React (`frontend/dist/`), montados en `/usr/share/nginx/html` en modo lectura (`:ro`). Incluye `try_files $uri $uri/ /index.html;` para permitir recargas y acceso directo a subrutas declarativas (`/monitor`, `/audit`, `/login`).

2. **`/api/` (Backend REST Spring Boot)**:
   - Configurado en `infra/nginx/nginx.conf`:
     ```nginx
     location /api/ {
         proxy_pass http://host.docker.internal:8080/api/;
         ...
     }
     ```
   - **Alcance desde Docker al notebook**: En `infra/docker-compose.yml`, el servicio `nginx` define `extra_hosts: ["host.docker.internal:host-gateway"]`.
     - En Docker Desktop (Windows/macOS), `host.docker.internal` resuelve directamente a la máquina anfitriona.
     - En Docker Engine (Linux), `host-gateway` mapea la IP de la interfaz bridge (típicamente `172.17.0.1`), permitiendo que Nginx en el contenedor alcance el backend Spring Boot corriendo en el host en el puerto `8080`.
     - Spring Boot (Tomcat embebido) escucha por defecto en `0.0.0.0:8080`, aceptando las peticiones reenviadas por Nginx.

3. **`/grafana/` (Paneles Embebidos de Monitoreo)**:
   - Proxy reverso hacia `http://grafana:3000/grafana/` dentro de la red interna de Docker (`tanques-net`).
   - Mantiene headers de WebSockets (`Upgrade` y `Connection "upgrade"`).

---

## 4. Guía de Despliegue y Puesta en Marcha

### Paso 1: Compilar el Frontend React
Dado que el directorio `frontend/dist/` no está versionado en el repositorio (ignorado en `.gitignore`), es **estrictamente obligatorio** compilar la SPA antes de iniciar Nginx para que el volumen montado contenga los archivos estáticos de producción:
```bash
cd frontend
npm install
npm run build
cd ..
```

### Paso 2: Configurar Variables de Entorno
Copiar el archivo de plantilla a `infra/.env` y definir credenciales reales seguras:
```bash
cp infra/.env.example infra/.env
# Editar infra/.env con tu editor favorito y definir una clave segura en MQTT_PASSWORD
```

### Paso 3: Inicializar Contraseñas de Mosquitto con init-passwords
El script generará el archivo `infra/mosquitto/passwords` (ignorado por Git). Si la contraseña está vacía o es `cambiar-esta-clave`, el script abortará la ejecución:
```bash
# Linux / macOS
infra/mosquitto/init-passwords.sh tanques <tu_password_real>

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File infra/mosquitto/init-passwords.ps1 -Username tanques -Password <tu_password_real>
```
*(Si ya configuraste `MQTT_PASSWORD` en `infra/.env`, podés ejecutar el script sin argumentos y tomará automáticamente dicho valor).*

### Paso 4: Iniciar Contenedores Docker
```bash
cd infra
docker compose up -d
```

### Paso 5: Verificación Manual

> **AVISO DE SEGURIDAD**: En los comandos que requieran `-P`, utilizá siempre la **contraseña real configurada en tu `infra/.env`**, nunca valores de ejemplo (`cambiar-esta-clave`) ni credenciales públicas.

- **Verificar servicios corriendo**:
  ```bash
  docker compose ps
  ```
- **Probar rechazo de acceso anónimo en Mosquitto**:
  ```bash
  docker compose exec mosquitto mosquitto_pub -t "tanques/test" -m "test"
  ```
  *(Debe responder: `Connection Refused: not authorised`)*

- **Probar publicación autenticada con QoS 1 en `tanques/cmd`**:
  ```bash
  docker compose exec mosquitto mosquitto_pub -u tanques -P <tu_password_real> -t "tanques/cmd" -q 1 -m "{\"cmd\":\"pump_on\",\"target\":\"pump\"}"
  ```
  *(Debe salir con código 0 sin errores)*

- **Verificar Frontend servido por Nginx**:
  Abrir [http://localhost/](http://localhost/) o [http://localhost/monitor](http://localhost/monitor).

- **Verificar Grafana**:
  Abrir [http://localhost/grafana](http://localhost/grafana).

---

## 5. Rotación de Credenciales y Token de InfluxDB

En InfluxDB 2.x, el modo de inicialización (`DOCKER_INFLUXDB_INIT_MODE=setup`) se ejecuta **únicamente la primera vez que se crea el volumen `influxdb_data`**. Si posteriormente se modifica el token (`INFLUX_TOKEN`) o la contraseña (`INFLUX_PASSWORD`) en `infra/.env`, InfluxDB ignora los nuevos valores y mantiene los existentes en el volumen de datos persistente.

Para rotar el token de InfluxDB o resetear las credenciales maestras:

1. **Detener la infraestructura y eliminar volúmenes persistentes**:
   ```bash
   cd infra
   docker compose down -v
   ```
   > ⚠️ **ADVERTENCIA**: El flag `-v` destruye todos los datos persistidos en `influxdb_data`, `grafana_data` y `mosquitto_data`.

2. **Actualizar las variables en `infra/.env`**:
   Configurar el nuevo valor de `INFLUX_TOKEN`, `INFLUX_PASSWORD` y `MQTT_PASSWORD`.

3. **Volver a levantar los contenedores**:
   ```bash
   docker compose up -d
   ```

4. **Regenerar obligatoriamente la clave de Mosquitto**:
   Dado que el volumen o estado del broker fue reinicializado, se debe regenerar el hash de contraseñas de Mosquitto:
   - **En Windows (PowerShell)**:
     ```powershell
     powershell -ExecutionPolicy Bypass -File mosquitto\init-passwords.ps1
     docker compose restart mosquitto
     ```
   - **En Linux / macOS**:
     ```bash
     infra/mosquitto/init-passwords.sh
     docker compose restart mosquitto
     ```

5. **Actualizar el token en los consumidores**:
   Recordar definir el nuevo `INFLUX_TOKEN` tanto en el backend Spring Boot (`$env:INFLUX_TOKEN`) como en el bridge Python (`$env:INFLUX_TOKEN`).

