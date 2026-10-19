# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto adhiere a [Conventional Commits](https://www.conventionalcommits.org/).

---

## [Unreleased]

### Added - Fase 4: Puesta en Marcha Integral (Etapa 1 - Mosquitto + Nginx Frontend)
- **Broker MQTT Mosquitto (`infra/docker-compose.yml`)**:
  - Incorporado servicio `tanques-mosquitto` con imagen fijada `eclipse-mosquitto:2.0.22` en el puerto `1883`.
  - Configuración estricta en `infra/mosquitto/mosquitto.conf` con `allow_anonymous false` y almacenamiento de contraseñas hasheadas en `infra/mosquitto/passwords`.
  - Scripts generadores de contraseñas multiplataforma (`infra/mosquitto/init-passwords.sh` y `infra/mosquitto/init-passwords.ps1`) utilizando el propio contenedor Docker para evitar dependencias locales del binario `mosquitto_passwd`, con validación estricta que aborta la ejecución si la contraseña está vacía o contiene el valor de ejemplo por defecto (`cambiar-esta-clave`).
  - Reglas en `.gitignore` para garantizar que el archivo `passwords` nunca sea commiteado al repositorio.
  - Tópicos definidos para el canal bidireccional de control con QoS 1: `tanques/cmd` (comandos del backend) y `tanques/ack` (confirmaciones/rechazos del bridge).
  - Regla de aislamiento de red documentada en `AGENTS.md` (uso obligatorio de red propia / hotspot en demostraciones en lugar de la red institucional).
- **Despliegue del Frontend Web en Nginx**:
  - Configurado montaje en volumen de solo lectura de `../frontend/dist` hacia `/usr/share/nginx/html` en el contenedor `tanques-nginx`.
  - Soporte de enrutamiento declarativo cliente para React Router mediante directiva `try_files $uri $uri/ /index.html;`, permitiendo navegación y recarga directa en subrutas (`/monitor`, `/audit`, `/login`).
  - Documentación de compilación, proxies y puesta en marcha en `infra/README.md`, actualización de `README.md` y unificación de variables en `.env.example` y `infra/.env.example`.

### Added - Fase 4: Puesta en Marcha Integral (Etapa 2 - Bridge con MQTT y Resiliencia Serial)
- **Canal Bidireccional de Comandos en `edge/bridge.py`**:
  - Incorporada integración con broker Mosquitto mediante librería `paho-mqtt==2.1.0` (pure Python sin extensiones C, compatible con Raspberry Pi 2 ARM 32-bit).
  - Suscripción a `tanques/cmd` y publicación en `tanques/ack` con **QoS 1**, `clean_session=True` y sin flag retain.
  - Validación de expiración de comandos en el borde: descarta comandos con antigüedad mayor a `COMMAND_MAX_AGE_MS` (default 5000 ms; 0 desactiva) según campo `ts` epoch ms y emite `{"ack": id, "ok": false, "reason": "expired"}` sin enviarlos al hardware.
  - Deduplicación idempotente de comandos por `id` en ventana deslizante de 100 elementos: republica el ack original si ya fue resuelto o ignora en silencio si aún se encuentra pendiente de respuesta física, sin emitir jamás acks de fallo con motivo `duplicate`.
  - Correlación asíncrona de acks por `id` con temporizador de 2.5 segundos: si el equipo físico no responde en ese lapso, emite `{"ack": id, "ok": false, "reason": "device_timeout"}`.
  - Arquitectura concurrente robusta: un único hilo lector dueño del descriptor serial/stdout, cola secuencial de salida (`queue.Queue`) y mapa de comandos pendientes protegido por `threading.Lock()`.
  - Discriminación por contenido entre tramas periódicas de telemetría (hacia InfluxDB 2.x) y tramas de respuesta ack (hacia Mosquitto MQTT).
  - Descarte seguro de líneas no JSON o ruido generado durante el auto-reset del Arduino Uno al conectarse el USB.
  - Reconexión tolerante con backoff exponencial ante caídas del broker MQTT, desconexiones del puerto serial físico o terminaciones del subproceso simulador.
- **Manejo de Tiempo e InfluxDB en Borde (Raspberry Pi 2 sin RTC)**:
  - Telemetría emitida en Line Protocol sin timestamp explícito por defecto (`use_server_timestamp=True`), permitiendo que InfluxDB aplique el sellado canónico oficial de recepción a nivel nanosegundo y protegiendo el histórico ante relojes desfasados al arrancar.
  - Opción `--use-local-timestamp` para sellado local en entornos con sincronización NTP verificada.
  - Chequeo de inicio con log de advertencia si el reloj del sistema reporta año menor a 2025 (desfase típico pre-NTP).
  - Verificada la compatibilidad nativa de Mosquitto 2.0.22 con la propiedad `MessageExpiryInterval` de MQTT v5.
- **Compatibilidad de Código y Dependencias**:
  - Declarada compatibilidad estricta con **Python 3.9+** (evitando sintaxis posterior como uniones PEP 604 en `edge/simulator.py` y `edge/bridge.py`).
  - Fijadas versiones exactas en `edge/requirements.txt`: `pyserial==3.5`, `pyyaml==6.0.2`, `influxdb-client==1.50.0` y `paho-mqtt==2.1.0`.
  - Documentada la adopción de `PyYAML==6.0.2` como versión LTS estándar en Debian/Raspberry Pi OS (6.0.3 solo añade wheels binarias para Python 3.13/3.14 free-threaded).
- **Seguridad y Servicio Systemd (`edge/systemd/tanques-bridge.service`)**:
  - Lectura de credenciales (`MQTT_PASSWORD`, `INFLUX_TOKEN`) desde variables de entorno o archivo `edge/.env` con permisos restringidos `chmod 600`.
  - Configurado usuario sin privilegios `User=pi`, `Group=pi` y grupo suplementario `SupplementaryGroups=dialout` para acceso a dispositivos seriales.
  - Ejemplos de uso en CLI sin contraseñas explícitas en parámetros de comando.
- **Herramienta de Diagnóstico (`edge/tools/send_cmd.py`)**:
  - Script para publicar comandos de prueba con `id`, valor booleano (`true`/`false`), edad artificial del timestamp (`age_s`) y target configurable.
- **Suite de Pruebas Automatizadas (20 tests en total)**:
  - Ejecución conjunta de `edge/test_edge.py` (10 tests de física, simulación e interlocks) y `edge/tests/test_bridge.py` (10 tests del bridge bidireccional, incluyendo test de arranque con broker caído `test_mqtt_broker_down_at_startup`).

### Added - Fase 4: Puesta en Marcha Integral (Etapa 3 - BridgeActuatorGateway Real con Paho MQTT y Resiliencia en Backend)
- **Cliente MQTT Eclipse Paho 1.2.5 (`backend/pom.xml`)**:
  - Incorporada dependencia `org.eclipse.paho:org.eclipse.paho.client.mqttv3:1.2.5` fijada exacta.
  - Registrada decisión consciente en `AGENTS.md`: la línea v3 se encuentra madura y altamente probada en producción aunque sin nuevos releases desde julio de 2020 (a reevaluar frente a Paho v5); Spring Integration MQTT se descartó por simplicidad para dos tópicos fijos.
- **Implementación de `BridgeActuatorGateway` en Perfil `prod`**:
  - Publicación de comandos en tópico `tanques/cmd` con **QoS 1**, `clean_session=true`, sin flag `retain`, identificador único `c_<random_hex>` y timestamp `ts` en epoch ms.
  - Correlación asíncrona de respuestas en `tanques/ack` mediante mapa concurrente de `CompletableFuture<BridgeAckMessage>`.
  - **Threading no bloqueante estricto**: La espera de confirmación (`.get(3, TimeUnit.SECONDS)`) se realiza exclusivamente en el hilo del request HTTP; el callback `messageArrived` de Paho se limita a completar el future en memoria, previniendo el congelamiento del hilo despachador MQTT.
  - **Resuscripción y Reconexión Automática**: Implementada interfaz `MqttCallbackExtended` que renueva la suscripción a `tanques/ack` (QoS 1) dentro de `connectComplete`. `clientId` único con sufijo aleatorio para evitar colisiones.
  - **Prevención de Fugas de Memoria**: Limpieza garantizada del mapa de comandos pendientes (`pendingAcks.remove(cmdId)`) en bloque `finally` para comandos resueltos, vencidos o interrumpidos.
  - **Arranque Tolerante a Broker Caído**: Bucle daemon en segundo plano (`connectLoop`) que intenta conectar a Mosquitto sin impedir el arranque del contenedor Spring Boot. Mientras el broker esté inaccesible, las solicitudes de control responden HTTP 503 (`reason: "bridge_unavailable"`).
  - **Mapeo Semántico de Códigos HTTP y Mensajes de Seguridad**:
    - Ack `ok=true` $\to$ HTTP 200 OK con confirmación auditada.
    - Ack `ok=false` con motivo de interlock (`overflow_a`, `overflow_b`, `sensor_fault`) $\to$ HTTP 409 Conflict.
    - Ack `ok=false` por `expired` o `device_timeout` $\to$ HTTP 503 Service Unavailable alertando que el estado físico es desconocido.
    - Timeout de espera (3 segundos) sin ack del bridge $\to$ HTTP 503 Service Unavailable (`reason: "bridge_unavailable"`).
- **Manejo de Estado Desconocido y Restricción de Encendido por Seguridad**:
  - En `InfluxTelemetryProvider`, seguimiento de `lastTelemetryTimestamp` y método `isTelemetryFresh()` (umbral de 5000 ms). Ante telemetría desactualizada, se reporta `{"pump": null}`, evitando asumir falsamente que la bomba está apagada.
  - `getActuatorsState()` en `BridgeActuatorGateway` delega en el proveedor de telemetría sin guardar estados ficticios en memoria.
  - **Interlock de telemetría obsoleta**: El backend rechaza cualquier comando de encendido (`value: true`) si la telemetría no es reciente ($> 5$ s), retornando HTTP 409 Conflict (`reason: "telemetry_stale"`) y registrándolo en auditoría; el apagado (`value: false`) permanece siempre habilitado por parada de emergencia.
- **Soporte de Frontend SPA (React + TypeScript)**:
  - Actualizados tipos en `frontend/src/types/telemetry.ts` (`actuators: Record<string, boolean | null>`, campo `message` opcional).
  - `PumpControl.tsx`: avatar y pill de estado ámbar (`avatar-unknown`, `state-unknown`) con etiqueta "DESCONOCIDO", advertencia explicativa de seguridad, botón "Encender Bomba" deshabilitado ante telemetría desactualizada, y botón "Forzar Apagado" habilitado para rol DOCENTE.
  - `MonitorView.tsx`: indicador dinámico de conexión del equipo calculado a partir de `dataUpdatedAt` de TanStack Query ("Equipo Conectado", "Sin datos recientes", "Equipo Desconectado").
  - `AuditTable.tsx`: columna y filtros compatibles con el atributo `target` persistido en base de datos H2 con valor por defecto `'pump'` para retrocompatibilidad.
- **Suite de Pruebas Automatizadas (35 tests backend exitosos)**:
  - 12 pruebas unitarias e integración en `BridgeActuatorGatewayTest`: comando exitoso (200), rechazo por interlock (409), rechazo de encendido por telemetría desactualizada (409 `telemetry_stale`), apagado permitido con telemetría vieja (200), comando expirado (503), timeout de dispositivo (503), timeout del gateway (503), broker desconectado (503), **test específico de reconexión tras caída del broker con recepción de acks**, telemetría fresca, telemetría obsoleta ($>5$ s $\to$ `null`) y target inválido (404).

### Added - Fase 4: Puesta en Marcha Integral (Etapa 4 - Verificación Integral E2E en Producción)
- **Verificación Integral de Punta a Punta**:
  - Ejecución y validación manual E2E de la arquitectura completa en perfil `prod` mediante 5 terminales concurrentes (Docker Compose, Bridge Edge, Backend Spring Boot, monitor Mosquitto Sub, y cliente REST/PowerShell).
  - Verificado el flujo exitoso de comando de encendido y apagado de bomba con confirmación por MQTT QoS 1 y respuesta HTTP 200 OK.
  - Verificado el disparo del interlock de seguridad de sobrellenado con respuesta HTTP 409 Conflict (`reason: "overflow_a"` / `"overflow_b"`).
  - Verificada la resiliencia y timeout ante bridge detenido con HTTP 503 Service Unavailable (`reason: "bridge_unavailable"`).
  - Verificada la resiliencia ante caída y reinicio del broker Mosquitto: reconexión automática transparente del backend y bridge sin reiniciar Spring Boot.
  - Verificada la segregación de seguridad por roles: usuario con rol `ALUMNO` recibe HTTP 403 Forbidden al intentar accionar actuadores.
  - Verificada la persistencia de eventos en la tabla de auditoría de H2 con mapeo correcto del campo `target` y motivos de rechazo.
  - Verificado el frontend SPA servido desde Nginx en `http://localhost/` consumiendo datos de telemetría y renderizando paneles de Grafana por iframe.

### Added - Fase 4: Puesta en Marcha Integral (Etapa 5 - Pulido, Resiliencia y Documentación Operativa)
- **Ajuste de Precisión Numérica en Dashboards de Grafana**:
  - Configurado `decimals = 1` en los gauges de nivel de Tanque A y Tanque B en `infra/grafana/provisioning/dashboards/json/tanques.json` (eliminando representación `0.100%` en favor de `0.1%`).
  - Configurado `decimals = 1` en el panel de series temporales de nivel histórico, `decimals = 2` en caudal de bomba (`L/min`) y `decimals = 1` en sensores de temperatura (`°C`).
- **Robustez de `InfluxTelemetryProvider` y Prevención de Fugas de Stack Trace**:
  - Captura y aislamiento de `InfluxException` y `UnauthorizedException` en `InfluxTelemetryProvider`: ante InfluxDB inaccesible, token inválido o ausencia de registros, retorna una trama de telemetría degradada con modo `"offline"`, indicador `sensor_fault: true`, estado de bomba desconocido (`"pump": null`) y `isTelemetryFresh() = false` sin propagar un error 500 no controlado.
  - Eliminada recursión mutua entre `getLatestTelemetry()` e `isTelemetryFresh()` calculando la frescura localmente a partir del timestamp del registro más reciente.
  - Incorporado manejador `@ExceptionHandler(InfluxException.class)` en `GlobalExceptionHandler` retornando HTTP 503 Service Unavailable (`reason: "telemetry_unavailable"`).
  - Incorporado `@ExceptionHandler(Throwable.class)` de respaldo en `GlobalExceptionHandler` para capturar cualquier error inesperado del servidor y devolver HTTP 500 con formato estructurado sin exponer stack traces a clientes externos.
  - Incorporadas pruebas unitarias completas en `InfluxTelemetryProviderTest` validando Influx caído, token no autorizado y resultado vacío.
- **Calibración de Interlocks y Documentación Operativa E2E**:
  - Confirmado umbral de seguridad de sobrellenado (85.0 %) configurable de manera desacoplada en `edge/config.yaml` y `backend/src/main/resources/application.yml`.
  - Documentada en `AGENTS.md` la nota sobre la inercia gravitatoria de descarga Tanque A $\to$ Tanque B (pico acumulado en B de hasta ~97 % en simulaciones con bomba apagada a tiempo) y la necesidad de calibración física y evaluación de corte preventivo por volumen total combinado ($V_A + V_B$).
  - Creada guía integral de verificación operativa en `docs/05-verificacion-e2e.md` detallando la puesta en marcha con 5 terminales, formatos reales de respuesta de API (`ActuatorCommandResponse` y `AuditEntryResponse`), uso de marcadores `<TU_CLAVE_...>` sin secretos reales, y notas de experiencia (variables de sesión `$env:`, resembrado de H2 borrando `backend/data`, sincronización de contraseñas de Mosquitto y comillas en perfiles de PowerShell 5.1).
- **Higiene del Repositorio y Auditoría de Secretos**:
  - Agregadas exclusiones a `.gitignore` para notas y scripts temporales de prueba (`ayuda.md`, `probar-e2e.ps1`, `*.local.md`).
  - Verificada la ausencia total de secretos reales en archivos versionados mediante auditoría con `git grep`.

### Added - Fase 4: Puesta en Marcha Integral (Etapa 6 - Firmware Arduino Uno - Sub-etapa 6.1)
- **Esqueleto Modular de Firmware (`firmware/tanques/`)**:
  - Implementada arquitectura modular en C/C++ dividida en `tanques.ino`, `config.h`, `actuadores`, `sensores` y `protocolo` para ATmega328P (16 MHz, 5 V).
  - Cumplimiento estricto de restricción de memoria: sin uso de heap (`malloc`/`free`), sin la clase `String` y sin `ArduinoJson`. Consumo ultra bajo medido por `arduino-cli`: **Flash: 3796 bytes (11%)** sobre 32 KB; **RAM: 355 bytes (17%)** sobre 2 KB.
  - Modo `#define MODO_SIM_SIN_SENSORES 1` en `config.h` para pruebas completas en banco con la placa Arduino Uno sin sensores periféricos conectados: emite telemetría periódica a 1 Hz con valores nulos (`null`) y bandera `sensor_fault: true`, duplicando el accionamiento de la bomba en el LED integrado del pin 13 (`LED_BUILTIN`).
  - Seguridad en Relé de Bomba (pin `D9`): garantizado estado **APAGADO** como primerísima instrucción en `setup()`, con lógica de conmutación configurable mediante `#define RELE_ACTIVO_ALTO` (1 o 0).
  - Parser serie en buffer estático (`SERIAL_RX_BUFFER_SIZE = 96`) con descarte seguro de tramas demasiado largas ante desbordes. Parseo sin librerías de comandos `{"id":"...","cmd":"set","target":"pump","value":true|false}` respondiendo con `{"ack":"<id>","ok":true}` o rechazo semántico (`"unknown_cmd"`, `"malformed_cmd"`).
- **Adaptación y Robustez en Borde (`edge/bridge.py`)**:
  - Modificado `format_influx_line` para tolerar campos de sensores nulos (`None`) en tramas JSON seriales (emitidas en `MODO_SIM_SIN_SENSORES` o ante `sensor_fault`) e insertar correctamente la línea en InfluxDB Line Protocol sin provocar excepciones `TypeError`.
  - Incorporada prueba unitaria `test_format_influx_line_with_null_sensors` en `edge/tests/test_bridge.py`.
- **Documentación de Hardware y Cableado (`docs/04-hardware.md`)**:
  - Creada especificación técnica completa con mapa de pines (`D0`-`D1` UART, `D2` Caudalímetro INT0, `D4`-`D7` HX711, `D8` OneWire, `D9` Relé, `D10`-`D11` NeoPixels, `D13` LED Diagnóstico).
  - Documentadas reglas de topología de alimentación: obligatoriedad de fuente externa de 5 V con GND común para cargas inductivas y tiras LED, capacitor de 1000 µF y resistencias de 330 Ω en líneas de datos NeoPixel.

### Planned (Fase 4 - Próximas Etapas)
- **Etapa 6 (Sub-etapa 6.2)**: Integración de sensores reales (OneWire/DallasTemperature DS18B20 sin bloqueo en loop, HX711 x2 con celdas de 10 kg, caudalímetro por interrupciones en D2 e interlock definitivo en firmware).
- **Etapa 6 (Sub-etapa 6.3)**: Tiras NeoPixel (barra de nivel, color por temperatura y parpadeo en alarma).
- **Etapa 6 (Sub-etapa 6.4)**: Simulación en Wokwi (`diagram.json`, `wokwi.toml`) y cierre documental.

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
