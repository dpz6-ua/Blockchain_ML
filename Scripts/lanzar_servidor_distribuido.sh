#!/usr/bin/env bash
# ==============================================================================
# Script para automatizar las 3 ejecuciones del Servidor en modo distribuido (PC 1)
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
EXP="${1:-E3}"
RUNS="${2:-3}"
ROUNDS="${3:-30}"

if command -v python3.12 >/dev/null 2>&1; then
    PY="python3.12"
else
    PY="python3"
fi

USA_BC=true
if [[ "$EXP" =~ ^E[23] ]] || [[ "$EXP" =~ [Nn][Oo] ]]; then
    USA_BC=false
fi

echo "=============================================================================="
echo "SERVIDOR DISTRIBUIDO AUTOMATIZADO (PC 1 - Estación Servidor)"
echo "Experimento:     $EXP"
echo "Runs a realizar: $RUNS"
echo "Rondas por run:  $ROUNDS"
echo "Capa Blockchain: $USA_BC"
echo "=============================================================================="

if [ "$USA_BC" = true ]; then
    echo "1. Desplegando instancia de FLRegistry en Besu para todo el experimento $EXP..."
    $PY "$DIR/contract_address.py" || { echo "Error desplegando contrato"; exit 1; }
    echo ""
    echo ">> RECUERDA: Si no lo has hecho ya, asegúrate de que 'Smart_Contracts/Contract_Data/FLRegistry_info.json'"
    echo "   esté copiado en el otro ordenador (PC 2) antes de lanzar los clientes."
    echo "=============================================================================="
    sleep 3
fi

for (( run=1; run<=RUNS; run++ ))
do
    echo ""
    echo "------------------------------------------------------------------------------"
    echo ">> [SERVIDOR] Iniciando Run $run de $RUNS para $EXP"
    echo "------------------------------------------------------------------------------"

    # Liberar puerto 8081 por si quedó algo activo
    fuser -k 8081/tcp 2>/dev/null || true
    sleep 2

    if [ "$USA_BC" = true ]; then
        echo "Arrancando Servidor con Blockchain (Run $run)..."
        echo "   (Esperando a que los clientes del PC 2 se conecten y completen las $ROUNDS rondas)"
        $PY "$DIR/server.py" --exp "$EXP" --run "$run" --rounds "$ROUNDS" --server-address "0.0.0.0:8081"
    else
        echo "Arrancando Servidor SIN Blockchain (Run $run)..."
        echo "   (Esperando a que los clientes del PC 2 se conecten y completen las $ROUNDS rondas)"
        $PY "$DIR/server_sin_bc.py" --exp "$EXP" --run "$run" --rounds "$ROUNDS" --server-address "0.0.0.0:8081"
    fi

    echo ">> Run $run del servidor finalizado con éxito."
    echo "Pausa de 5 segundos antes de preparar el siguiente run..."
    sleep 5
done

echo ""
echo "=============================================================================="
echo "Todos los runs de $EXP en el servidor han finalizado."
echo "Copia las métricas de los clientes desde el PC 2 y ejecuta analizar_metricas.py"
echo "=============================================================================="

