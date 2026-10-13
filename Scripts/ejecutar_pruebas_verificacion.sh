#!/usr/bin/env bash
# ==============================================================================
# Script de Ejecución de Pruebas de Verificación y Seguridad Criptográfica
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
ENDPOINT="${1:-http://localhost:18545}"

echo "=============================================================================="
echo "BANCO DE PRUEBAS EXPERIMENTALES DE VERIFICACIÓN CRUZADA"
echo "=============================================================================="

# 1. Asegurar despliegue de contrato
echo "1. Verificando/desplegando contrato FLRegistry..."
python3 "$DIR/contract_address.py" --endpoint "$ENDPOINT"

# 2. Ejecutar la batería de pruebas de verificación criptográfica
echo ""
echo "2. Ejecutando pruebas de detección de adulteración..."
python3 "$DIR/test_verificacion.py" --endpoint "$ENDPOINT"

echo ""
echo "=============================================================================="
echo "Pruebas de verificación completadas."
echo "=============================================================================="

