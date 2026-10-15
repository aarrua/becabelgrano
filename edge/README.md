# Edge Computing: Simulador Físico y Bridge Serial (UTN FRSF / GITDA)

Este directorio contiene los componentes que corren en el nodo de borde (*Edge Node* en Raspberry Pi) encargados de la simulación física de la planta didáctica, la ingesta de telemetría y la persistencia en base de datos temporal (InfluxDB 2.x).

---

## 1. Componentes

- **`simulator.py`**: Simulador físico en tiempo real de dos tanques acoplados en serie con bomba de impulsión, interlocks de seguridad automáticos (corte en $>95\%$), dinámica térmica pasiva y receptor de comandos JSON por `stdin`.
- **`bridge.py`**: Ingestor de telemetría serial o simulada. Aplica el sellado de tiempo UTC oficial de ingesta en el borde (*timestamping*), transforma la trama JSON a InfluxDB Line Protocol y persiste en InfluxDB 2.x.
- **`config.yaml`**: Parámetros de geometría de los tanques (áreas y alturas útiles), calibración de descarga y constantes de simulación.

---

## 2. Instalación de Dependencias

Se requiere Python 3.10+:

```bash
pip install -r edge/requirements.txt
```

*(Nota: Tanto `simulator.py` como `bridge.py` poseen módulos de contingencia con la biblioteca estándar de Python, por lo que pueden operar en entornos sin paquetes externos instalados para pruebas locales).*

---

## 3. Modo de Uso

### 3.1 Ejecutar el Simulador

```bash
# Modo estándar (1 Hz, emitiendo 1 trama JSON por segundo)
python edge/simulator.py

# Aceleración de tiempo 5x con bomba inicialmente encendida (para probar interlock rápido)
python edge/simulator.py --speed 5 --pump-on

# Pasar configuración personalizada
python edge/simulator.py --config edge/config.yaml --speed 10
```

#### Envío de Comandos en Caliente al Simulador

El simulador escucha por su entrada estándar (`stdin`) comandos JSON terminados en `\n` y responde inmediatamente con el acuse de recibo (`ack`):

```bash
# Encender bomba
{"id":"c1","cmd":"set","target":"pump","value":true}

# Apagar bomba
{"id":"c2","cmd":"set","target":"pump","value":false}

# Respuesta esperada:
# {"ack": "c1", "ok": true}
# O si hay sobrellenado:
# {"ack": "c1", "ok": false, "reason": "overflow_a"}
```

---

### 3.2 Ejecutar el Bridge

#### Opción A: Usando el Simulador Interno (para desarrollo sin hardware)

```bash
python edge/bridge.py --source sim --sim-speed 5
```

#### Opción B: Mediante Tubería UNIX / PowerShell (Piping)

```bash
python edge/simulator.py --speed 5 | python edge/bridge.py --source stdin
```

#### Opción C: Conectado al ESP32 por Puerto Serial Físico

```bash
# En Linux / Raspberry Pi
python edge/bridge.py --source serial:/dev/ttyUSB0:115200

# En Windows
python edge/bridge.py --source serial:COM3:115200
```

---

## 4. Características de Resiliencia del Bridge

1. **Prevención de Reseteo del ESP32**: En el modo serial, `bridge.py` fuerza `dtr=False` y `rts=False` **antes** de abrir el puerto, evitando que la activación de líneas de control de flujo resetee el microcontrolador.
2. **Reconexión Automática con Backoff**: Si el cable USB/serial se desconecta físicamente o el microcontrolador se apaga, el bridge no crashea; entra en un bucle de reintento exponencial ($1s, 2s, 4s, \dots, 30s$) y reanuda la ingesta transparentemente en cuanto el puerto vuelve a estar disponible.
3. **Validación de Integridad**: Descarta tramas corruptas, líneas no JSON o ruido inicial sin interrumpir el flujo.
