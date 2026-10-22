# Guía de la Demo "Caudal Real" (Fase 4)

Procedimiento para correr la demostración en la que **solo el caudalímetro es real**: un Arduino
Uno conectado por USB (firmware actual, `MODO_SIM_SIN_SENSORES 0`) emite telemetría con
`flow_lpm` real. El nivel, la temperatura y la bomba siguen viniendo del simulador
(`edge/bridge.py --source sim`). No interviene ninguna Raspberry Pi: todo corre en la misma PC
Windows que ejecuta el script.

---

## 1. Qué es real y qué es simulado

| Magnitud / Actuador | Origen en esta demo |
| :--- | :--- |
| Caudal (`flow_lpm`) | **Real.** Arduino Uno con el caudalímetro, por USB (puerto configurable, default `COM4`). |
| Nivel de Tanque A y B | Simulado (`edge/simulator.py`, vía `bridge.py --source sim`). |
| Temperatura de Tanque A y B | Simulado. |
| Bomba de impulsión | **Simulada.** El botón de la SPA solo enciende/apaga la bomba del simulador. |
| Bomba física (si existe en el kit) | Manual: el docente la opera a mano, fuera del sistema. El botón de la web **no** la controla. |

El dashboard de Grafana (`infra/grafana/provisioning/dashboards/json/tanques.json`) rotula cada
panel según este criterio: los paneles de nivel y temperatura dicen "(simulado)", el de caudal
dice "(real)", y arriba de todo hay un cartel de texto recordando la distinción.

---

## 2. Requisitos previos

- JDK 21 Temurin instalado en `C:\Program Files\Eclipse Adoptium` (el script elige automáticamente
  la carpeta `jdk-21*` más nueva que encuentre ahí).
- Maven (`mvn`) y Docker Desktop (con `docker compose`) disponibles en el `PATH`.
- `infra/.env` creado a partir de `infra/.env.example`, con `INFLUX_TOKEN`, `INFLUX_PASSWORD`,
  `GRAFANA_ADMIN_PASSWORD` y `MQTT_PASSWORD` completados (ver `infra/README.md`). El script carga
  este archivo en el entorno de la sesión sin mostrar los valores en pantalla.
- El entorno virtual de Python en `edge/.venv` con las dependencias de `edge/requirements.txt`
  instaladas (si no existe, el script cae a `python` del `PATH`).
- Sin `-SinCaudal`: el Arduino Uno del caudalímetro conectado por USB en el puerto configurado en
  el script (`$PuertoCaudal`, default `COM4`). Verificar el puerto real en el Administrador de
  Dispositivos antes de arrancar.
- Red propia para la jornada (router Wi-Fi dedicado o hotspot portátil propio). **Nunca** la red
  institucional (ver `AGENTS.md`, punto 10).

---

## 3. Cómo correr la demo

Desde una terminal de **Windows PowerShell 5.1** en la raíz del repositorio:

```powershell
.\scripts\iniciar-demo.ps1
```

El script, en orden:

1. Fija `JAVA_HOME` y `Path` al JDK 21 de Eclipse Adoptium.
2. Carga `infra\.env` en el entorno de la sesión (sin mostrar los valores).
3. Define `INFLUX_URL` (si no vino de `infra\.env`, usa `http://localhost:8086`).
4. Genera un `JWT_SECRET` aleatorio de 256 bits, válido solo para esta sesión.
5. Pide por teclado (`Read-Host`, sin eco en pantalla) las contraseñas iniciales de `DOCENTE` y
   `ALUMNO`.
6. Verifica que las seis variables obligatorias (`JAVA_HOME`, `INFLUX_URL`, `INFLUX_TOKEN`,
   `JWT_SECRET`, `DOCENTE_PASSWORD`, `ALUMNO_PASSWORD`) estén definidas; si falta alguna, aborta
   sin levantar nada.
7. Levanta `docker compose up -d` desde `infra/` (InfluxDB, Grafana, Mosquitto, Nginx) y espera a
   que InfluxDB responda en `/health`.
8. Abre una ventana nueva de PowerShell con el bridge (`edge/bridge.py --source sim
   --flow-serial <puerto>`).
9. Abre otra ventana nueva con el backend Spring Boot en perfil `prod`
   (`mvn spring-boot:run "-Dspring-boot.run.profiles=prod"`).

Al terminar, el script imprime las URLs de acceso (frontend/Nginx, Swagger, Grafana directo) y
recuerda que la bomba real es siempre manual. Las dos ventanas nuevas quedan abiertas: cerrarlas
detiene el bridge y el backend respectivamente. Los contenedores de Docker se detienen por
separado con `docker compose down` desde `infra/`.

### Plan B: sin caudalímetro real (`-SinCaudal`)

Si el Arduino del caudalímetro no está disponible (no llegó, se rompió, no hay puerto libre),
correr:

```powershell
.\scripts\iniciar-demo.ps1 -SinCaudal
```

Esto omite `--flow-serial`: el bridge corre 100% con el simulador, incluyendo el caudal. El resto
del procedimiento (Docker, backend en `prod`, SPA) es idéntico. Es la opción recomendada para
ensayar el guion de la demo sin el hardware a mano.

---

## 4. Compilar la SPA con el cartel de demo (`VITE_DEMO_BANNER`)

La SPA puede mostrar un cartel opcional debajo de la barra superior (navbar) con el texto de la
variable de entorno `VITE_DEMO_BANNER`, documentada en `frontend/.env.example`. Si no está
definida, no se muestra ningún cartel (comportamiento normal fuera de la demo).

```powershell
cd frontend
copy .env.example .env.local   # si todavía no existe
# Editar .env.local y descomentar/completar, por ejemplo:
#   VITE_DEMO_BANNER=Demostración: nivel, temperatura y bomba simulados; caudal real.
npm run build
```

El build (`npm run build`) deja el resultado en `frontend/dist/`, que es lo que Nginx sirve
(`infra/docker-compose.yml` monta `../frontend/dist` como solo lectura). Recompilar y relanzar
Nginx (o `docker compose restart nginx` desde `infra/`) después de cualquier cambio en `.env.local`
para que el cartel tome efecto, ya que Vite incrusta la variable en tiempo de build.

---

## 5. Notas y pendientes de verificación

- Este procedimiento fue redactado y revisado en código y en los tests automatizados del bridge
  (`edge/tests/test_bridge.py`), pero **no se verificó todavía contra el hardware real del
  caudalímetro ni con `docker compose` y el backend en `prod` corriendo en simultáneo** en esta
  sesión de trabajo; antes de la jornada presencial, ensayar el script completo de punta a punta
  (con y sin `-SinCaudal`) con el Arduino Uno real conectado.
- Si el puerto real del caudalímetro no es `COM4`, editar `$PuertoCaudal` al principio de
  `scripts/iniciar-demo.ps1`.
- Ante cualquier error de `docker compose up -d` (por ejemplo, Docker Desktop no iniciado), el
  script aborta sin abrir las ventanas del bridge ni del backend.
