# Guía de Pruebas y Puesta en Marcha de Hardware (Fase 4 - Sub-etapa 6.2)

> **Destinatario:** Personal técnico y desarrolladores a cargo del armado, cableado y calibración electrónica del kit didáctico en UTN FRSF.  
> **Microcontrolador:** Arduino Uno R3 (ATmega328P, 16 MHz, 5V).  
> **Velocidad de Comunicación Serie:** **115200 bps** (8 bits de datos, sin paridad, 1 bit de parada, fin de línea `NL` y `CR`).

---

## 1. Resumen de Pines y Cableado

| Señal / Componente | Pin Arduino Uno | Nivel Lógico | Notas de Conexión |
|---|:---:|:---:|---|
| **Caudalímetro (Hall)** | **D2** (INT0) | 5V / Pulsos | Pin D2 con interrupción externa. Conectar señal amarilla. Alimentar con 5V y GND. |
| **HX711 Tanque A (DOUT)** | **D4** | 5V | Datos de la celda de carga del Tanque A (superior). |
| **HX711 Tanque A (SCK)** | **D5** | 5V | Clock del convertidor HX711 Tanque A. |
| **HX711 Tanque B (DOUT)** | **D6** | 5V | Datos de la celda de carga del Tanque B (inferior). |
| **HX711 Tanque B (SCK)** | **D7** | 5V | Clock del convertidor HX711 Tanque B. |
| **DS18B20 (Bus OneWire)** | **D8** | 5V | Bus común para ambos sensores. **Obligatoria resistencia pull-up de 4.7 kΩ entre D8 y 5V**. |
| **Relé Bomba (Señal IN)** | **D9** | 5V (Alto = ON) | Entrada del módulo relé/MOSFET. Estado en reposo/arranque: **0V / LOW (Apagado)**. |
| **NeoPixel Tanque A** | **D10** | 5V | Tira LED WS2812B nivel A (sub-etapa 6.3). Resistencia en serie recomendada: 330 Ω. |
| **NeoPixel Tanque B** | **D11** | 5V | Tira LED WS2812B nivel B (sub-etapa 6.3). Resistencia en serie recomendada: 330 Ω. |
| **LED Testigo en Placa** | **D13** | Built-in | Duplica visualmente el estado del relé de la bomba. |
| **Serial USB (TX / RX)** | **D0 / D1** | 5V TTL | Reservado para comunicación con Raspberry Pi / PC. **No conectar periféricos**. |

---

## 1.1 PASO OBLIGATORIO: Calibrar celdas y caudalímetro ANTES de conectar la bomba real

> **ADVERTENCIA DE SEGURIDAD:** No conectar la bomba real a la alimentación ni hacer circular agua hasta completar este paso y su lista de verificación (sección 1.1.6).

### 1.1.1 Por qué es obligatorio

El firmware calcula el nivel de cada tanque así (`firmware/tanques/sensores.cpp`):

```text
peso_g    = (lectura_cruda - tara) / escala
level_pct = peso_g / capacidad_maxima_g * 100
```

Los valores de fábrica en `firmware/tanques/calibracion.cpp` son **nominales, de ejemplo**: tara `0`, escala `420` cuentas/g, capacidad `4000 g` (A) y `2450 g` (B), y `450` pulsos/L para el caudalímetro (YF-S201). Con esos valores **`level_pct` es incorrecto**. Como el interlock de sobrellenado (`overflow_a` / `overflow_b`, umbral 85 %) y el corte automático de la bomba se evalúan sobre `level_pct`, **un nivel subestimado puede no activar el interlock y el tanque puede desbordar**. Un caudal mal calibrado distorsiona además `flow_lpm`.

### 1.1.2 Preparación

1. En `firmware/tanques/config.h`: `MODO_SIM_SIN_SENSORES` en `0`. Con `1` los interlocks por sensores están **deshabilitados**, por lo que **nunca** se debe conectar la bomba real en ese modo.
2. Cargar las direcciones DS18B20 reales y poner `DS18B20_SON_DIRECCIONES_DE_EJEMPLO` en `0` (Prueba 2 de esta guía).
3. Con la bomba **desconectada** (el módulo relé puede quedar conectado como testigo).

### 1.1.3 Capacidad máxima y factor K (comandos `set_capacity` y `cal_flow`)

La capacidad máxima de cada tanque y el factor K del caudalímetro se fijan por comando serie. Quedan en RAM hasta ejecutar `save_cal`; no hace falta recompilar ni recargar el sketch. Los valores de fábrica siguen en `calibracion_reset_defaults()`.

| Comando | Campos | Rango aceptado | Rechazo (`reason`) |
| :--- | :--- | :--- | :--- |
| `set_capacity` | `tank` (`"a"`/`"b"`), `grams` | 100 a 10000 g | `invalid_capacity` |
| `cal_flow` | `pulses_per_l` | 10 a 10000 pulsos/L | `invalid_flow_k` |

Un valor fuera de rango, no numérico o con un `tank` distinto de `a`/`b` se rechaza con `{"ack":"...","ok":false,"reason":"..."}` y **no modifica nada**.

1. Medir la capacidad útil real de cada tanque (la masa de agua, en gramos, que corresponde al 100 %) y enviar:
   ```json
   {"cmd":"set_capacity","tank":"a","grams":4000}
   {"cmd":"set_capacity","tank":"b","grams":2450}
   ```
2. **Calibrar el caudalímetro** (sin usar la bomba): pasar por el caudalímetro, a mano o por gravedad, un volumen conocido (por ejemplo 1 L medido con una jarra graduada) a caudal aproximadamente constante y cronometrar el tiempo `T`. Calcular el caudal real `V / T` en L/min y compararlo con el promedio de `flow_lpm` de la telemetría durante esa pasada. Repetir al menos 3 veces y promediar:
   $$K_{nuevo} = K_{actual} \times \frac{\text{flow\_lpm medido}}{\text{caudal real}}$$
   Enviar el resultado:
   ```json
   {"cmd":"cal_flow","pulses_per_l":450}
   ```
3. Ejecutar `save_cal` cuando los valores sean los definitivos (Paso C de la sección 4). Sin `save_cal`, un `RESET` o un corte de energía restaura lo guardado en la EEPROM (o los valores de fábrica).
4. Con el bridge en marcha, los comandos se envían por MQTT con `id` único (ver "Calibrar con el sistema armado", sección 4).

> `reset_cal` restaura **todos** los parámetros (tara, escala, capacidad y K) a los valores de fábrica en RAM y deja el equipo **sin calibrar**: el encendido de la bomba se rechaza con `not_calibrated` hasta volver a fijar tara, escala y capacidad de ambos tanques.
>
> El firmware considera el equipo calibrado si la calibración viene de una EEPROM válida o si en la sesión se fijaron `tare`, `cal_scale` y `set_capacity` de **ambos** tanques. `save_cal` se rechaza con `not_calibrated` si no se cumple, para no persistir valores de fábrica. La capacidad por defecto es 2000 g (menor que el cilindro más chico).

### 1.1.4 Celdas de carga: tara y escala con peso conocido

Seguir la sección 4 (Prueba 3) completa, para **ambos** tanques:

1. **Tara** con la plataforma vacía y estable (`tare`).
   > **La tara se hace SIEMPRE con el tanque vacío y la bomba apagada.** Si se tara con agua en el tanque, ese peso queda como "cero": el nivel se lee menor que el real y el corte por sobrellenado llega tarde (el tanque se llena más allá del umbral antes de que el firmware lo detecte). Por eso el firmware rechaza `tare` con `reason: "pump_on"` si la bomba está encendida; lo que no puede detectar es agua ya presente en el tanque, eso es responsabilidad de quien calibra.
2. **Escala** con una masa patrón conocida (`cal_scale`), usando la fórmula de la sección 4. Para mejores resultados, usar una masa cercana al rango de operación.
3. Verificar con una segunda masa distinta que `weight_g` coincide con el valor real. Criterio sugerido: error menor al 2 % en ambos tanques; si no, repetir la escala.
4. Persistir con `save_cal` y comprobar tras un `RESET` del Arduino que los valores se conservan.

### 1.1.5 Comprobar el interlock de nivel con la calibración hecha

Con la bomba aún desconectada, cargar el tanque con una masa/volumen conocido equivalente a más del 85 % de la capacidad máxima y confirmar `overflow_a` u `overflow_b` en `true` y el rechazo del encendido (Prueba 5, Caso B). Repetir para **ambos** tanques: el umbral de 85 % aplica a cualquiera de los dos.

### 1.1.6 Lista de verificación previa a conectar la bomba

- [ ] `MODO_SIM_SIN_SENSORES` en `0` y direcciones DS18B20 reales.
- [ ] Capacidad de A y B (`set_capacity`) igual a la capacidad real medida.
- [ ] Factor K (`cal_flow`) calibrado con volumen conocido.
- [ ] Tara y escala de A y B calibradas y verificadas con una segunda masa.
- [ ] `save_cal` ejecutado y persistencia comprobada tras un `RESET`.
- [ ] Interlock `overflow_a` / `overflow_b` comprobado a 85 % en ambos tanques.
- [ ] Valores finales (tara, escala, capacidad, K) anotados en la bitácora del kit.

---

## 2. Prueba 1: Relé de Bomba y Watchdog de Seguridad (Sin Sensores)

Esta prueba verifica el accionamiento seguro de la bomba y el corte automático por tiempo continuo (watchdog de 60 segundos). Puede realizarse con el Arduino solo o con el módulo relé conectado.

1. Abrir `firmware/tanques/config.h` y asegurar temporalmente:
   ```cpp
   #define MODO_SIM_SIN_SENSORES 1
   ```
2. Cargar el sketch `firmware/tanques/tanques.ino` en el Arduino Uno.
3. Abrir el Monitor Serie de Arduino IDE (o terminal serial) configurado a **115200 baud**, con terminación **Ambos NL & CR**.
4. **Verificación de encendido**:
   - Enviar por la línea de comandos:
     ```json
     {"id":"c1","cmd":"set","target":"pump","value":true}
     ```
   - **Resultado esperado**:
     - Respuesta en monitor serie:
       ```json
       {"ack":"c1","ok":true}
       ```
     - El LED integrado (pin 13) se ilumina de inmediato.
     - El módulo relé conmuta a cerrado (se escucha el "clic" mecánico y enciende su LED testigo).
5. **Verificación de renovación del Watchdog**:
   - Si se vuelve a enviar `{"id":"c2","cmd":"set","target":"pump","value":true}` antes de los 60 segundos, el temporizador se reinicia a cero sin interrumpir la operación.
6. **Verificación de corte por Watchdog (60 segundos)**:
   - Dejar correr la bomba sin enviar ningún comando durante 60 segundos.
   - **Resultado esperado**:
     - Exactamente a los 60 segundos, la bomba se apaga automáticamente por hardware (relé abre, LED 13 se apaga).
     - La trama periódica de telemetría refleja:
       ```json
       "alarms":{"overflow_a":false,"overflow_b":false,"sensor_fault":...,"pump_timeout":true}
       ```
7. **Verificación de apagado manual**:
   - Enviar `{"id":"c3","cmd":"set","target":"pump","value":false}`.
   - La respuesta es `{"ack":"c3","ok":true}` y la alarma `pump_timeout` vuelve a `false`.

---

## 3. Prueba 2: Escaneo y Asignación de Sensores DS18B20

Los sensores Dallas DS18B20 comparten el pin digital **D8**. Cada sensor físico tiene una dirección única de 64 bits grabada de fábrica.

1. Conectar los dos sensores DS18B20 al pin D8 con una resistencia de **4.7 kΩ entre el pin D8 (DATA) y 5V**.
2. Abrir y cargar en el Arduino el sketch auxiliar:
   `firmware/utilidades/leer_direcciones/leer_direcciones.ino`.
3. Abrir el Monitor Serie a **115200 baud**.
4. **Resultado esperado en consola**:
   ```text
   ========================================================
    UTN FRSF / GITDA - Lector de Direcciones DS18B20
    Bus OneWire en Pin Digital: D8 (Pull-up 4.7k a 5V)
   ========================================================

   Iniciando escaneo de bus OneWire...

   [Sensor #1 detectado]
     Tipo: Dallas DS18B20 (Genuino / Compatible)
     Direccion C++: { 0x28, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x01 }
     Temperatura leida: 23.50 °C

   [Sensor #2 detectado]
     Tipo: Dallas DS18B20 (Genuino / Compatible)
     Direccion C++: { 0x28, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x02 }
     Temperatura leida: 23.25 °C
   ```
5. **Identificación física de los tanques**:
   - Tomar uno de los sensores entre los dedos durante 5 segundos.
   - El monitor serie mostrará el aumento de temperatura en ese sensor específico.
   - Asignar ese sensor al **Tanque A** o al **Tanque B** según corresponda físicamente.
6. **Configuración en el Firmware principal**:
   - Abrir `firmware/tanques/config.h` y pegar las direcciones obtenidas:
     ```cpp
     #define DS18B20_ADDR_A { 0x28, ... }
     #define DS18B20_ADDR_B { 0x28, ... }
     #define DS18B20_SON_DIRECCIONES_DE_EJEMPLO 0
     ```

---

## 4. Prueba 3: Celdas de Carga y Calibración HX711

El kit utiliza dos convertidores HX711 de 24 bits para medir el peso del líquido en cada tanque.

1. Conectar los módulos HX711 a los pines D4/D5 (Tanque A) y D6/D7 (Tanque B).
2. Asegurar en `firmware/tanques/config.h`:
   ```cpp
   #define MODO_SIM_SIN_SENSORES 0
   ```
3. Cargar `firmware/tanques/tanques.ino` y abrir el Monitor Serie a **115200 baud**.

### Paso A: Tara con Tanques Vacíos
1. Con las plataformas de los tanques completamente vacías y estables, enviar:
   ```json
   {"cmd":"tare","tank":"a"}
   ```
   Respuesta esperada: `{"ack":"cal","ok":true}`.
2. Hacer lo propio con el tanque B:
   ```json
   {"cmd":"tare","tank":"b"}
   ```
   Respuesta esperada: `{"ack":"cal","ok":true}`.
3. Observar la telemetría periódica: `"weight_g"` y `"level_pct"` deben indicar `0.0` en ambos tanques.

### Paso B: Calibración con Masa Patrón Conocida
1. Colocar un peso conocido sobre la celda del Tanque A (por ejemplo, una botella con 1000 ml = 1000 g de agua).
2. Observar el campo `"weight_g"` en la telemetría periódica.
3. Si el peso medido difiere de 1000 g, calcular el nuevo factor:
   $$\text{Nuevo Scale} = \text{Scale Actual (420.0)} \times \frac{\text{Peso Medido}}{\text{Peso Real (1000.0)}}$$
4. Ajustar el factor enviando el comando:
   ```json
   {"cmd":"cal_scale","tank":"a","scale":415.8}
   ```
   Respuesta esperada: `{"ack":"cal","ok":true}`.
5. Repetir el procedimiento para el Tanque B (`"tank":"b"`).

### Paso C: Guardado Permanente en EEPROM
1. **IMPORTANTE**: La calibración queda solo en memoria RAM temporal hasta que se guarde explícitamente.
2. Para persistirla en la EEPROM interna, enviar:
   ```json
   {"cmd":"save_cal"}
   ```
   Respuesta esperada: `{"ack":"cal","ok":true}`.
3. **Comprobación de persistencia**: Presionar el botón `RESET` del Arduino Uno. Al reiniciar, el firmware cargará automáticamente los valores calibrados desde la EEPROM verificando su checksum.

### Calibrar con el sistema armado (vía bridge y MQTT)

Los comandos `tare`, `cal_scale`, `set_capacity`, `cal_flow`, `reset_cal` y `save_cal` **atraviesan el bridge hasta el puerto serie**: `edge/bridge.py` no filtra por nombre de comando y reenvía al Arduino cualquier JSON válido que traiga `id`. Por eso se puede calibrar con el kit completo en marcha, sin detener el bridge ni desconectar nada.

Particularidades:

- **El `id` es obligatorio.** El bridge descarta sin avisar al emisor cualquier comando sin `id` (solo lo registra en su log). Los ejemplos de los pasos A, B y C de arriba, sin `id`, solo sirven conectándose directo al Arduino por el Monitor Serie.
- **Longitud del `id`: hasta 36 caracteres** (alcanza para un UUID con guiones). Un `id` más largo no se reconoce y el comando se rechaza como `missing_id`/`unknown_cmd`.
- **El `id` debe ser único.** El bridge deduplica por `id` en una ventana de 100 comandos. Reusar un `id` ya procesado no reenvía nada al Arduino y republica el ack anterior.
- **El ack llega con el `id` enviado** (`{"ack":"<id>","ok":true}`) en el tópico `tanques/ack`. Si el Arduino no responde en 2,5 s, el bridge publica `{"ack":"<id>","ok":false,"reason":"device_timeout"}`.
- **No hay endpoint REST ni botón en la SPA.** El backend solo expone `/api/actuators/{name}`. La calibración se hace publicando en MQTT, por lo tanto **no queda en la auditoría de H2** y solo requiere las credenciales de Mosquitto.
- Con el bridge en marcha, **no abrir el Monitor Serie** al mismo tiempo: el puerto serie admite un único proceso.
- Calibrar siempre con la **bomba apagada**.

Procedimiento (desde la Raspberry Pi, en `infra/`):

1. En una terminal, dejar escuchando los acks:
   ```bash
   docker compose exec mosquitto mosquitto_sub -t "tanques/ack" -u tanques -P "<TU_CLAVE_MOSQUITTO>" -v
   ```
2. En otra terminal, publicar cada comando con un `id` nuevo. Ejemplo de tara del Tanque A con el tanque vacío:
   ```bash
   docker compose exec mosquitto mosquitto_pub -t "tanques/cmd" -u tanques -P "<TU_CLAVE_MOSQUITTO>" \
     -q 1 -m '{"id":"cal-tare-a-1","cmd":"tare","tank":"a"}'
   ```
   Se espera ver en la primera terminal: `tanques/ack {"ack":"cal-tare-a-1","ok":true}`.
3. Repetir con el resto de los comandos (cada uno con su `id` propio):
   ```text
   {"id":"cal-tare-b-1","cmd":"tare","tank":"b"}
   {"id":"cal-scale-a-1","cmd":"cal_scale","tank":"a","scale":415.8}
   {"id":"cal-scale-b-1","cmd":"cal_scale","tank":"b","scale":415.8}
   {"id":"cal-cap-a-1","cmd":"set_capacity","tank":"a","grams":4000}
   {"id":"cal-cap-b-1","cmd":"set_capacity","tank":"b","grams":2450}
   {"id":"cal-flow-1","cmd":"cal_flow","pulses_per_l":450}
   {"id":"cal-reset-1","cmd":"reset_cal"}
   {"id":"cal-save-1","cmd":"save_cal"}
   ```
4. Verificar el resultado en `weight_g` y `level_pct` de la telemetría (SPA, Grafana o `mosquitto_sub -t "tanques/#"` si corresponde) antes de pasar al siguiente comando.
5. Ejecutar `save_cal` solo cuando los valores sean los definitivos. `reset_cal` restaura los valores por defecto **solo en RAM**; lo guardado en EEPROM se recupera con un reinicio del Arduino.

---

## 5. Prueba 4: Caudalímetro de Efecto Hall

1. Conectar el caudalímetro al pin **D2** (interrupción INT0).
2. Con el sketch `firmware/tanques/tanques.ino` en ejecución, hacer circular agua o soplar suavemente a través de la boquilla del caudalímetro.
3. **Resultado esperado**:
   - En la trama periódica emitida cada 1 segundo por el monitor serie, el campo `"flow_lpm"` dejará de reportar `0.00` y reflejará el caudal instantáneo medido en litros por minuto (ej. `"flow_lpm": 2.15`).
   - Al detener el flujo, el valor retornará suavemente a `0.00`.

---

## 6. Prueba 5: Interlocks de Seguridad (Sobrellenado y Falla)

El firmware del Arduino Uno contiene lógica de interlock autónomo en hardware para proteger la instalación física:

### Caso A: Rechazo por Falla de Sensores (`sensor_fault`)
> Desconectar el bus DS18B20 **no** dispara este caso: la temperatura pasa a `temp_c: null` pero `sensor_fault` no cambia y el encendido no se rechaza por ese motivo.

1. Desconectar los cables DOUT de los módulos HX711.
2. En la telemetría se reportará `"sensor_fault": true`.
3. Intentar encender la bomba:
   ```json
   {"id":"cmd_safe_1","cmd":"set","target":"pump","value":true}
   ```
4. **Resultado esperado**:
   - Comando **RECHAZADO**:
     ```json
     {"ack":"cmd_safe_1","ok":false,"reason":"sensor_fault"}
     ```
   - La bomba **NO** se enciende, evitando operar a ciegas.

### Caso B: Corte Automático por Sobrellenado (`overflow_a` / `overflow_b`)
1. Con la bomba encendida, aplicar presión manual en la celda del Tanque A o Tanque B hasta superar el 85% de capacidad (`>= 85.0%`).
2. **Resultado esperado**:
   - En el instante en que el nivel alcanza el 85%, el relé se desconecta de inmediato por hardware sin esperar comandos externos.
   - La telemetría refleja:
     ```json
     "alarms":{"overflow_a":true,"overflow_b":false,"sensor_fault":false,"pump_timeout":false}
     ```
3. Intentar encender la bomba mientras persiste el sobrellenado:
   ```json
   {"id":"cmd_safe_2","cmd":"set","target":"pump","value":true}
   ```
4. **Resultado esperado**:
   - Comando rechazado con motivo específico:
     ```json
     {"ack":"cmd_safe_2","ok":false,"reason":"overflow_a"}
     ```

### Caso C: Apagado Preventivo Siempre Permitido
1. Aún con fallas activas o sobrellenado, el comando de apagado siempre es aceptado:
   ```json
   {"id":"cmd_safe_3","cmd":"set","target":"pump","value":false}
   ```
2. **Resultado esperado**:
   ```json
   {"ack":"cmd_safe_3","ok":true}
   ```

---

## 7. Pruebas de la revisión de seguridad del firmware

Hacer estas pruebas con la **bomba real desconectada** (usar una lámpara o el LED `D13` como testigo del relé). `MODO_SIM_SIN_SENSORES` en `0` salvo que se indique.

### Caso 7.1: Cable de celda cortado con la bomba encendida (fail-safe)
1. Con el equipo calibrado y ambos niveles válidos, encender la bomba (`set`/`pump`/`true`, ack `ok:true`).
2. Desconectar el cable de datos (DOUT) de la celda/HX711 del Tanque A (o del B).
3. **Esperado**: en la trama siguiente (≤ 1 s) `alarms.sensor_fault` en `true`, `level_pct` y `weight_g` de ese tanque en `null`, `actuators.pump` en `false`, y la lámpara se apaga. La bomba no queda encendida sin vigilancia.
4. Intentar encender de nuevo: ack `{"ok":false,"reason":"sensor_fault"}`. Reconectar el cable: el `sensor_fault` se limpia solo y se puede volver a encender.
5. Repetir con el cable de la celda puesto a +5 V/GND para forzar un valor saturado (plausibilidad): `sensor_fault` en `true` y niveles `null`.

### Caso 7.2: Plausibilidad del peso (sin recorte a 0)
1. Con la plataforma vacía y tarada, el `weight_g` puede mostrar valores levemente negativos (p. ej. `-3.2`): ya no se recortan a 0; `level_pct` se acota a `0.0`.
2. Quitar la masa tras tarar con una masa encima (peso < -50 g, `HX711_PESO_MIN_PLAUSIBLE_G`): **esperado** `sensor_fault` en `true` y `weight_g`/`level_pct` en `null`. Volver a tarar con la plataforma vacía.

### Caso 7.3: Calibración faltante (`not_calibrated`)
1. Con la EEPROM sin guardar (o tras `reset_cal`), reiniciar el Uno y enviar `{"id":"nc1","cmd":"set","target":"pump","value":true}`.
2. **Esperado**: `{"ack":"nc1","ok":false,"reason":"not_calibrated"}`; con el backend: HTTP 409 con `reason: "not_calibrated"` y mensaje específico en la SPA.
3. `{"id":"nc2","cmd":"save_cal"}` en ese estado: también `not_calibrated`.
4. Enviar `tare` y `cal_scale` de A y B y `set_capacity` de A y B (todos `ok:true`): el encendido pasa a aceptarse. Un solo comando faltante mantiene el rechazo.
5. `save_cal`, `RESET` del Uno: sigue aceptando el encendido sin recalibrar (EEPROM válida).
6. `{"id":"nc3","cmd":"reset_cal"}`: vuelve a rechazar con `not_calibrated`.
7. El apagado (`value:false`) se acepta siempre.

### Caso 7.4: Relé con lámpara (`PERMITIR_BOMBA_SIN_CALIBRAR`)
1. Conectar una lámpara a 220 V **solo** a través del módulo relé, con la bomba y el agua fuera del circuito. Poner `PERMITIR_BOMBA_SIN_CALIBRAR` en `1` (el compilador mostrará un `#warning`) y cargar el sketch.
2. Con sensores conectados pero sin calibrar, `set`/`pump`/`true` enciende la lámpara y `false` la apaga. Con sensores desconectados sigue rechazando por `sensor_fault`; para probar solo el relé usar `MODO_SIM_SIN_SENSORES 1`.
3. **Volver `PERMITIR_BOMBA_SIN_CALIBRAR` a `0` y recargar** antes de conectar la bomba real.

### Caso 7.5: Reset del Uno con el relé
1. Con la lámpara conectada y la bomba encendida, presionar `RESET` en el Uno y luego reconectar el USB (reinicia el Uno).
2. **Esperado**: la lámpara se apaga y **no** se enciende ni parpadea durante el arranque (relé activo en alto o en bajo: `digitalWrite` del nivel de apagado antes de `pinMode`). Tras el arranque, `actuators.pump` es `false`. Observar con un osciloscopio o con la lámpara sobre un relé activo en bajo (`RELE_ACTIVO_ALTO 0`).
3. Verificar que la bomba **no** se reenciende sola tras el reset.

### Caso 7.6: `cal_scale` con valores inválidos
Enviar `{"id":"s1","cmd":"cal_scale","tank":"a","scale":0}`, `"scale":-5`, `"scale":1e999` y `"scale":200000`. **Esperado**: `{"ack":"s1","ok":false,"reason":"invalid_scale"}` en todos y la escala vigente sin cambios.

### Caso 7.6b: `tare` con la bomba encendida
Con la bomba encendida (lámpara de prueba) enviar `{"id":"t0","cmd":"tare","tank":"a"}`. **Esperado**: `{"ack":"t0","ok":false,"reason":"pump_on"}` y la tara vigente sin cambios. Apagar la bomba y repetir: `ok:true`.

### Caso 7.7: `tare` con el HX711 no listo
El `tare` promedia 10 muestras (`HX711_TARE_MUESTRAS`) y puede tardar ~1 s con el HX711 a 10 Hz (tope de 2 s, `HX711_TARE_TIMEOUT_MS`); el ack llega recién al terminar. Desconectar el HX711 del Tanque A y enviar `{"id":"t1","cmd":"tare","tank":"a"}`. **Esperado**: `{"ack":"t1","ok":false,"reason":"sensor_not_ready"}`; al reconectar, la tara anterior sigue vigente hasta un `tare` exitoso.

### Caso 7.8: Ids largos
Enviar un `set` con `id` de 36 caracteres (`"id":"123e4567-e89b-12d3-a456-426614174000"`) con el campo `"ts"` incluido. **Esperado**: el ack vuelve con el mismo `id` completo.

### Caso 7.9: HX711 sin conectar o sin alimentar
Con el Uno solo (sin módulo HX711, o con el módulo sin alimentar), la línea DOUT queda atascada y el crudo es exactamente `0` (o `-1`). Antes se informaba `weight_g 0.0` / `level_pct 0.0` como válidos; ahora se trata como lectura inválida (`HX711_RAW_TODO_CEROS` / `HX711_RAW_TODO_UNOS`).
0. Con el pull-up interno en DOUT (compensación del error de la librería 0.7.5), un DOUT suelto lee alto y el HX711 figura "no listo"; el crudo `0`/`-1` solo aparece si el módulo está sin alimentar o la línea queda atascada.
1. Con `MODO_SIM_SIN_SENSORES 0` y sin HX711 conectado, observar la telemetría. **Esperado**: `weight_g` y `level_pct` en `null` en el tanque afectado y `alarms.sensor_fault` en `true`.
2. `{"id":"hx1","cmd":"tare","tank":"a"}`. **Esperado**: `{"ack":"hx1","ok":false,"reason":"sensor_not_ready"}`.
3. `{"id":"hx2","cmd":"set","target":"pump","value":true}`. **Esperado**: `{"ack":"hx2","ok":false,"reason":"sensor_fault"}` y el relé sigue apagado.
4. Conectar y alimentar el HX711: el `sensor_fault` se limpia solo y los valores vuelven a ser numéricos.
