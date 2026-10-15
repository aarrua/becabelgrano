# Kit Didáctico de Tanques Interconectados (UTN FRSF / GITDA)

Sistema de monitoreo y control web para el kit didáctico de dos tanques acoplados en serie, desarrollado en el marco de proyectos de Industria 4.0 e Internet de las Cosas (IoT) de la Universidad Tecnológica Nacional - Facultad Regional Santa Fe.

---

## 1. Arquitectura General del Sistema

La solución opera de forma autónoma en el borde (*Edge Computing*) sobre una Raspberry Pi, con un único punto de entrada HTTP mediante un reverse proxy **nginx**:

```mermaid
graph TD
    subgraph Campo ["Capa Física / Simulación"]
        ESP32["ESP32 / edge/simulator.py<br/>(Sensores, Bomba, Interlocks)"]
    end

    subgraph Edge ["Raspberry Pi (Edge Node)"]
        Bridge["edge/bridge.py<br/>(Ingesta & Timestamping)"]
        Influx[("InfluxDB 2.x<br/>(Base Temporal TSDB)")]
        Grafana["Grafana<br/>(Dashboards Kiosk / Viewer)"]
        
        subgraph BackendSpring ["Backend (Spring Boot 3.x - Java 21)"]
            API["REST Controllers (/api)"]
            Sec["Spring Security (JWT / RBAC)"]
            H2[("H2 Database<br/>(Usuarios & Auditoría)")]
            GW["ActuatorGateway<br/>(Validación & Interlocks)"]
            TP["TelemetryProvider"]
        end

        Nginx["nginx (Reverse Proxy :80)"]
    end

    subgraph Clientes ["Capa de Presentación Web"]
        Front["Frontend Web (React + TS)"]
        Docente(("Docente<br/>(Monitoreo + Control)"))
        Alumno(("Alumno<br/>(Solo Lectura)"))
    end

    %% Flujo Telemetría
    ESP32 -->|"Serial JSON (115200 bps)"| Bridge
    Bridge -->|"Line Protocol (Write)"| Influx
    Influx -->|"Flux / InfluxQL"| Grafana
    Influx -.->|"Telemetría Histórica"| TP
    TP --> API

    %% Flujo Comandos
    Docente -->|"Acceso Web"| Front
    Alumno -->|"Acceso Web"| Front
    Front -->|"HTTP / (Static)"| Nginx
    Front -->|"HTTP /api (REST + JWT)"| Nginx
    Front -->|"HTTP /grafana (iFrame)"| Nginx

    Nginx -->|"Proxy /api"| API
    Nginx -->|"Proxy /grafana"| Grafana
    
    API --> Sec
    Sec --> GW
    GW -->|"Comando JSON"| Bridge
    Bridge -->|"Serial JSON"| ESP32
    API --> H2
```

---

## 2. Estructura del Repositorio

```text
.
├── AGENTS.md        # Reglas, convenciones y decisiones arquitectónicas para agentes y devs
├── README.md        # Documento principal del proyecto
├── docs/            # Documentación técnica en Markdown (compatible con Obsidian)
│   ├── 01-contrato-datos.md   # Especificación de telemetría y tramas seriales
│   ├── 02-flujo-comandos.md   # Diagramas de secuencia y mecanismos de seguridad
│   └── 03-api.md              # Documentación de endpoints REST y OpenAPI
├── firmware/        # Especificación y código para ESP32
├── edge/            # Scripts Python para Raspberry Pi (simulador físico y bridge serial)
├── backend/         # Backend REST en Spring Boot 3 (Java 21, Maven, JWT, H2)
├── infra/           # Orquestación con Docker Compose (InfluxDB, Grafana, nginx)
└── frontend/        # Aplicación SPA en React + Vite + TypeScript (Fase 3)
```

---

## 3. Estado de Fases del Proyecto

| Fase | Descripción | Estado |
|---|---|:---:|
| **Fase 0** | Reglas de repositorio, contratos de datos, flujos de interlock y documentación base | **Completada** |
| **Fase 1** | Simulador físico de tanques, bridge serial, InfluxDB, Grafana y nginx | *Pendiente* |
| **Fase 2** | Backend Spring Boot (JWT, roles DOCENTE/ALUMNO, ActuatorGateway, auditoría H2) | *Pendiente* |
| **Fase 3** | Frontend React SPA (Monitoreo, paneles Grafana embebidos, control seguro) | *Pendiente* |

---

## 4. Convenciones de Desarrollo

Para consultar las reglas de desarrollo, lineamientos de commits convencionales y alcance técnico, consultar [`AGENTS.md`](file:///c:/Users/Ale/OneDrive%20-%20UTN%20-%20Santa%20Fe/UTN%202025/Beca%20Belgrano/becabelgrano/AGENTS.md).
