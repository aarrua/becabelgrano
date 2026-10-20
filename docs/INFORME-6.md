# Informe final - Etapa 6 (calibración, NeoPixel 6.3 y Wokwi 6.4)

Rama: `feature/fase-4-firmware-auto` (la indicada en el prompt era `feature/fase-4-firmware`; ver `docs/DECISIONES-6.md`).

## Qué se hizo por tarea

1. **Calibración**: nuevos comandos `set_capacity` (`tank`, `grams`, 100-10000 g, rechazo `invalid_capacity`) y `cal_flow` (`pulses_per_l`, 10-10000, rechazo `invalid_flow_k`). Validan rango y NaN, no modifican nada si rechazan, persisten solo con `save_cal`. El bridge ya reenviaba cualquier comando con `id`; se agregaron 3 casos parametrizados y un test de ack de rechazo. Documentados en `firmware/GUIA_PRUEBAS_HARDWARE.md` (secciones 1.1.3 y 4).
2. **6.3 NeoPixel**: `firmware/tanques/indicadores.cpp/.h`. Barra de nivel por tanque, brillo constante 20/255, color por temperatura, último LED rojo parpadeante en alarma, refresco no bloqueante, sin falla con tiras desconectadas. Documentación eléctrica (5 V externo, GND común, 330 Ω, 1000 µF) en `docs/04-hardware.md` sección 5.
3. **6.4 Wokwi**: `firmware/wokwi/diagram.json`, `wokwi.toml` y `README.md`. Qué no simula Wokwi: `docs/04-hardware.md` sección 6.1.
4. **Documentación**: `CHANGELOG.md`, `README.md`, `AGENTS.md`, `firmware/README.md`, `docs/DECISIONES-6.md`.
5. **Verificación**: salidas abajo.

## Commits (Conventional)

```
feat(firmware): agregar comandos set_capacity y cal_flow con validacion de rangos
test(edge): cubrir set_capacity y cal_flow en el paso por el bridge
docs(firmware): documentar set_capacity y cal_flow en la guia de pruebas
feat(firmware): agregar barras de nivel NeoPixel por tanque
feat(firmware): agregar simulacion Wokwi y documentar NeoPixel en hardware
docs(repo): cerrar Etapa 6 en CHANGELOG, README, AGENTS e informes
```

## Salida real

`python -m pytest edge/ -q`:
```
.................................                                        [100%]
33 passed in 3.04s
```

`arduino-cli compile --fqbn arduino:avr:uno firmware/tanques`:
```
Sketch uses 17504 bytes (54%) of program storage space. Maximum is 32256 bytes.
Global variables use 799 bytes (39%) of dynamic memory, leaving 1249 bytes for local variables. Maximum is 2048 bytes.
```
Límites: flash < 80 %, RAM < 75 %. Cumplidos. Los 48 bytes de pixeles NeoPixel se reservan en heap y no están incluidos en el 39 %.

`arduino-cli compile --fqbn arduino:avr:uno firmware/utilidades/leer_direcciones`:
```
Sketch uses 7694 bytes (23%) of program storage space. Maximum is 32256 bytes.
Global variables use 243 bytes (11%) of dynamic memory, leaving 1805 bytes for local variables. Maximum is 2048 bytes.
```

No se subió ningún sketch. No se leyó ni escribió `infra/.env`.

## Sin probar por falta de hardware

- Los comandos `set_capacity` y `cal_flow` solo se probaron en el bridge (reenvío) y por compilación; el parser del firmware no se ejecutó en un Uno.
- NeoPixel: no se vio encendido en tiras reales. Sin medir: consumo, brillo, colores y si `show()` (~250 µs con interrupciones cortadas) pierde bytes seriales o pulsos del caudalímetro.
- Wokwi: el `diagram.json` no se abrió en Wokwi (sin `wokwi-cli` ni cuenta); nombres de pines y tipos de componente sin validar.
- Todo lo de calibración física (celdas, capacidad, factor K, umbral 85 %, corte por volumen combinado), direcciones DS18B20 reales y vista en celular, según los pendientes de `AGENTS.md`.
