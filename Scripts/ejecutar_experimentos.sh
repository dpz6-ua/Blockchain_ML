#!/usr/bin/env bash
# ==============================================================================
# Script de Automatización de Experimentos FL + Blockchain (E1 a E5)
# Permite ejecutar múltiples repeticiones (runs) por configuración
# y consolidar automáticamente los resultados estadísticos.
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
EXP="${1:-E1}"
RUNS="${2:-3}"
ROUNDS="${3:-30}"
SERVER_IP="${4:-localhost}"

if command -v python3.12 >/dev/null 2>&1; then
    PY="python3.12"
else
    PY="python3"
fi

echo "=============================================================================="
echo "ORQUESTADOR DE EXPERIMENTOS FEDERADOS"
echo "Experimento:         $EXP"
echo "Número de runs:      $RUNS"
echo "Rondas por run:      $ROUNDS"
echo "IP del Servidor:     $SERVER_IP"
echo "=============================================================================="

# Determinar si el experimento usa Blockchain
USA_BC=true
if [[ "$EXP" =~ ^E[23] ]] || [[ "$EXP" =~ [Nn][Oo] ]]; then
    USA_BC=false
fi

for (( run=1; run<=RUNS; run++ ))
do
    echo ""
    echo "------------------------------------------------------------------------------"
    echo ">> Iniciando Ejecución $run de $RUNS para el Experimento $EXP"
    echo "------------------------------------------------------------------------------"

    if [ "$USA_BC" = true ]; then
        echo "1. Desplegando instancia limpia del contrato FLRegistry en Hyperledger Besu..."
        $PY "$DIR/contract_address.py" || { echo "Error desplegando contrato"; exit 1; }

        echo "2. Arrancando Servidor Flower con soporte Blockchain..."
        $PY "$DIR/server.py" --exp "$EXP" --run "$run" --rounds "$ROUNDS" > "$DIR/server_${EXP}_run${run}.log" 2>&1 &
        SERVER_PID=$!
        echo "   Servidor lanzado con PID $SERVER_PID. Esperando que abra el puerto 8081..."
        for i in {1..45}; do
            if (echo > /dev/tcp/127.0.0.1/8081) 2>/dev/null; then
                echo "   Servidor listo en puerto 8081."
                sleep 2
                break
            fi
            sleep 1
        done

        echo "3. Arrancando Cliente Member 2..."
        $PY "$DIR/client.py" --member 2 --exp "$EXP" --run "$run" --server-ip "$SERVER_IP" > "$DIR/client2_${EXP}_run${run}.log" 2>&1 &
        CLIENT2_PID=$!

        echo "4. Arrancando Cliente Member 3..."
        $PY "$DIR/client.py" --member 3 --exp "$EXP" --run "$run" --server-ip "$SERVER_IP" > "$DIR/client3_${EXP}_run${run}.log" 2>&1 &
        CLIENT3_PID=$!

    else
        echo "1. Arrancando Servidor Flower Baseline SIN Blockchain..."
        $PY "$DIR/server_sin_bc.py" --exp "$EXP" --run "$run" --rounds "$ROUNDS" > "$DIR/server_${EXP}_run${run}.log" 2>&1 &
        SERVER_PID=$!
        echo "   Servidor lanzado con PID $SERVER_PID. Esperando que abra el puerto 8081..."
        for i in {1..30}; do
            if (echo > /dev/tcp/127.0.0.1/8081) 2>/dev/null; then
                echo "   Servidor listo en puerto 8081."
                sleep 1
                break
            fi
            sleep 1
        done

        echo "2. Arrancando Cliente Member 2 (sin BC)..."
        $PY "$DIR/client_sin_bc.py" --member 2 --exp "$EXP" --run "$run" --server-ip "$SERVER_IP" > "$DIR/client2_${EXP}_run${run}.log" 2>&1 &
        CLIENT2_PID=$!

        echo "3. Arrancando Cliente Member 3 (sin BC)..."
        $PY "$DIR/client_sin_bc.py" --member 3 --exp "$EXP" --run "$run" --server-ip "$SERVER_IP" > "$DIR/client3_${EXP}_run${run}.log" 2>&1 &
        CLIENT3_PID=$!
    fi

    echo "Esperando finalización de los procesos..."
    wait $CLIENT2_PID || echo "Aviso: Cliente 2 terminó"
    wait $CLIENT3_PID || echo "Aviso: Cliente 3 terminó"
    wait $SERVER_PID || echo "Aviso: Servidor terminó"

    echo ">> Ejecución $run completada con éxito."
done

echo ""
echo "=============================================================================="
echo "Todas las ejecuciones de $EXP han finalizado."
echo "Ejecutando consolidación estadística..."
echo "=============================================================================="
$PY "$DIR/analizar_metricas.py"

