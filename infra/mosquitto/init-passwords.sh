#!/usr/bin/env bash
# ==============================================================================
# Generador de archivo de contraseñas para Mosquitto (UTN FRSF / GITDA)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASSWORDS_FILE="${SCRIPT_DIR}/passwords"

# 1. Determinar credenciales (argumentos > variables de entorno > .env > defaults)
USER="${1:-${MQTT_USER:-}}"
PASSWORD="${2:-${MQTT_PASSWORD:-}}"

if [ -z "$USER" ] || [ -z "$PASSWORD" ]; then
    ENV_FILE="${SCRIPT_DIR}/../.env"
    if [ -f "$ENV_FILE" ]; then
        if [ -z "$USER" ]; then
            USER="$(grep -E '^MQTT_USER=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '\r' || true)"
        fi
        if [ -z "$PASSWORD" ]; then
            PASSWORD="$(grep -E '^MQTT_PASSWORD=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '\r' || true)"
        fi
    fi
fi

USER="${USER:-tanques}"
PASSWORD="${PASSWORD:-tanques123}"

echo "Generando archivo de credenciales Mosquitto para el usuario: '$USER'..."

# 2. Generar archivo con mosquitto_passwd local o mediante contenedor Docker
if command -v mosquitto_passwd &> /dev/null; then
    mosquitto_passwd -c -b "$PASSWORDS_FILE" "$USER" "$PASSWORD"
else
    docker run --rm -v "${SCRIPT_DIR}:/mosquitto/config" eclipse-mosquitto:2.0.22 mosquitto_passwd -c -b /mosquitto/config/passwords "$USER" "$PASSWORD"
fi

# 3. Permisos seguros para el archivo generado
chmod 644 "$PASSWORDS_FILE" 2>/dev/null || true

echo "✓ Archivo de contraseñas generado con éxito en: $PASSWORDS_FILE"
echo "  Usuario configurado: $USER"
