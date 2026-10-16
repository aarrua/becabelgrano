#!/usr/bin/env bash
# ==============================================================================
# Generador de archivo de contraseñas para Mosquitto (UTN FRSF / GITDA)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASSWORDS_FILE="${SCRIPT_DIR}/passwords"

# 1. Determinar credenciales (argumentos > variables de entorno > .env)
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

# Validar que la contraseña no esté vacía ni sea el placeholder inseguro
if [ -z "$PASSWORD" ] || [ "$PASSWORD" = "cambiar-esta-clave" ]; then
    echo "ERROR: Debe definir una contraseña válida para Mosquitto (MQTT_PASSWORD)." >&2
    echo "No se permite utilizar la contraseña vacía ni el valor de ejemplo 'cambiar-esta-clave'." >&2
    echo "Configure una contraseña segura en infra/.env (MQTT_PASSWORD=...) o pásela por parámetro:" >&2
    echo "  $0 [usuario] <contraseña-segura>" >&2
    exit 1
fi

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
