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
1. Desconectar los cables DOUT de los módulos HX711 o el bus DS18B20.
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
