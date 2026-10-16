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

### 2.1 Configuración de Seguridad
Mosquitto opera con **autenticación obligatoria por usuario y contraseña** (`allow_anonymous false`). Las contraseñas están almacenadas de forma hasheada (PBKDF2-SHA512) en el archivo `infra/mosquitto/passwords`.

> **Seguridad**: El archivo `passwords` **nunca se commitea al repositorio** (ignorado por `.gitignore`). Debe ser generado en el entorno de despliegue mediante el script provisto.

### 2.2 Generación del Archivo de Contraseñas
Para generar o actualizar el archivo `infra/mosquitto/passwords`, se proveen scripts multiplataforma que utilizan la propia imagen Docker de Mosquitto para evitar dependencias locales:

- **En Linux / macOS / Git Bash**:
  ```bash
  cd infra/mosquitto
  chmod +x init-passwords.sh
  ./init-passwords.sh
  ```
  *(Opcionalmente se pueden pasar credenciales específicas: `./init-passwords.sh <usuario> <contraseña>`)*

- **En Windows (PowerShell)**:
  ```powershell
  cd infra\mosquitto
  .\init-passwords.ps1
  ```
  *(Opcionalmente: `.\init-passwords.ps1 -Username tanques -Password mi_password`)*

El script lee por defecto las credenciales desde `infra/.env` (`MQTT_USER` y `MQTT_PASSWORD`), aplicando `tanques` / `tanques123` como fallback de desarrollo.

### 2.3 Tópicos y QoS
El broker Mosquitto administra los tópicos del canal bidireccional de control entre el backend y el edge:
- **`tanques/cmd`**: El Backend Spring Boot publica órdenes de control de actuadores en formato JSON (especificado en `docs/01-contrato-datos.md`) con **QoS 1**.
- **`tanques/ack`**: El Bridge Python suscribe al hardware/simulador y publica la confirmación o rechazo del comando con **QoS 1**.

---

## 3. Nginx: Punto de Entrada Único y Servidor del Frontend

El contenedor **Nginx** unifica el acceso en el puerto 80:
- **`/`**: Sirve los archivos estáticos de la aplicación React SPA compilada (`frontend/dist/`), montada como volumen de solo lectura. Incorpora `try_files $uri $uri/ /index.html;` para permitir el enrutamiento declarativo del lado del cliente (React Router) ante recargas o accesos directos a subrutas (`/monitor`, `/audit`, `/login`).
- **`/api/`**: Redirige peticiones REST al Backend Spring Boot (`http://host.docker.internal:8080/api/`).
- **`/grafana/`**: Redirige al servidor de dashboards Grafana con soporte de WebSockets (`Upgrade` y `Connection "upgrade"`).

---

## 4. Guía de Despliegue y Puesta en Marcha

### Paso 1: Configurar Variables de Entorno
Copiar el archivo de ejemplo si no existe:
```bash
cp infra/.env.example infra/.env
```

### Paso 2: Compilar el Frontend React
Generar los estáticos de producción en `frontend/dist/`:
```bash
cd frontend
npm install
npm run build
cd ..
```

### Paso 3: Inicializar Contraseñas de Mosquitto
```bash
# Linux / macOS
infra/mosquitto/init-passwords.sh

# Windows
powershell -ExecutionPolicy Bypass -File infra/mosquitto/init-passwords.ps1
```

### Paso 4: Iniciar Contenedores Docker
```bash
cd infra
docker compose up -d
```

### Paso 5: Verificación
- **Frontend SPA**: `http://localhost/`
- **Ruta directa React Router**: `http://localhost/monitor`
- **Broker MQTT**: `localhost:1883` (probar publicación autenticada con usuario `tanques`)
- **Grafana**: `http://localhost/grafana`
- **InfluxDB**: `http://localhost:8086`
