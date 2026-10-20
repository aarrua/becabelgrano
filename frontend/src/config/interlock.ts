/**
 * Umbral de corte por sobrellenado que se muestra en la SPA (solo visualización).
 * La decisión de interlock la toman el firmware y las alarmas overflow_a/overflow_b;
 * este valor debe coincidir con firmware/tanques/config.h, edge/config.yaml y application.yml.
 */
const parsed = Number(import.meta.env.VITE_OVERFLOW_THRESHOLD_PCT)

export const OVERFLOW_THRESHOLD_PCT: number =
  Number.isFinite(parsed) && parsed > 0 && parsed < 100 ? parsed : 85
