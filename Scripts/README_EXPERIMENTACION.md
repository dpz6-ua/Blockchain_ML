# Guía de Experimentación Ampliada: Blockchain + Federated Learning + IPFS

Esta guía describe cómo ejecutar y analizar la batería de pruebas ampliada para el artículo científico y Trabajo de Fin de Grado (TFG).

---

## 1. Revisión de la Medición del Tiempo por Ronda

### Problema Identificado en la Versión Previa:
- Los datos del **Cuadro III** del artículo original (*E1: 89,37 s, E2: 84,15 s, E3: 64,26 s, E4: 71,29 s, E5: 70,88 s*) medían únicamente el tiempo que cada cliente pasaba dentro de su método `fit()`.
- En el código con Blockchain (`client.py`), el tiempo incluía la verificación descendente en IPFS, el entrenamiento local (3 épocas), la subida a IPFS y la confirmación de `registerClientModel` en Besu.
- En el código sin Blockchain (`client_sin_bc.py`), solo medía el entrenamiento local.
- **La transacción del servidor (`updateModel`, entre 4,8 s y 6,9 s) quedaba fuera** de la medición del tiempo de ronda del cliente, a pesar de que el texto del artículo afirmaba incluirla.

### Solución Implementada:
Ahora todos los scripts miden de forma simétrica y exhaustiva en dos niveles complementarios:

1. **Nivel Servidor (Tiempo de Ronda Extremo a Extremo)**:
   - Se mide desde el despacho de la ronda a los clientes en `configure_fit` hasta el término de la agregación y confirmación en bloque de `updateModel` en `aggregate_fit`.
   - Campos registrados en `server.csv`:
     - `tiempo_total_ronda_seg`: Duración real de la ronda federada completa.
     - `tiempo_espera_clientes_seg`: Tiempo de comunicación y entrenamiento en clientes.
     - `tiempo_verif_clientes_seg`: Auditoría on-chain de CIDs en Besu (`getClientModel`).
     - `tiempo_agregacion_fedavg_seg`: Cómputo matemático de FedAvg.
     - `tiempo_subida_ipfs_seg`: Subida del nuevo modelo consolidado a IPFS.
     - `tiempo_confirmacion_tx_seg`: Inclusión de `updateModel` en un bloque IBFT 2.0.
     - `gas_consumido`: Gas exacto consumido.
     - `clientes_validos` y `clientes_descartados`.

2. **Nivel Cliente (Tiempo de Ciclo Local y Desglose de Fases)**:
   - Campos registrados en `client_X.csv`:
     - `tiempo_total_cliente_seg`: Mantiene la comparabilidad histórica directa con el Cuadro III.
     - `tiempo_verif_desc_seg`: Consulta on-chain + descarga IPFS + `np.allclose` (0 en sin-BC).
     - `tiempo_entrenamiento_seg`: Entrenamiento PyTorch puro (idéntico en con y sin BC).
     - `tiempo_subida_ipfs_seg`: Subida a IPFS (0 en sin-BC).
     - `tiempo_confirmacion_bc_seg`: Transacción `registerClientModel` (0 en sin-BC).
     - `gas_real`: Gas del cliente.
     - `estado`: `EXITOSO` o `ABORTADO_POR_DISCREPANCIA`.

---

## 2. Repetición de Experimentos (3 Runs por Configuración)

Para evitar depender de una única ejecución y obtener medias, medianas y desviaciones típicas robustas con intervalos de confianza:

### Ejecución Manual por Terminal:
```bash
# Ejemplo: Experimento E1 (Monomáquina, con Blockchain, 4 validadores), Ejecución 1
python contract_address.py
python server.py --exp E1 --run 1 --rounds 30
python client.py --member 2 --exp E1 --run 1
python client.py --member 3 --exp E1 --run 1

# Para el Run 2 de E1:
python contract_address.py
python server.py --exp E1 --run 2 --rounds 30
python client.py --member 2 --exp E1 --run 2
python client.py --member 3 --exp E1 --run 2
```

### Ejecución Automatizada:
El script `ejecutar_experimentos.sh` orquesta automáticamente las 3 ejecuciones consecutivas, desplegando un contrato limpio en cada run para evitar colisiones de estado on-chain:
```bash
./ejecutar_experimentos.sh <ID_EXP> <NUM_RUNS> <NUM_RONDAS> [IP_SERVIDOR]

# Ejemplos:
./ejecutar_experimentos.sh E1 3 30 localhost   # 3 runs completos de E1
./ejecutar_experimentos.sh E2 3 30 localhost   # 3 runs completos de E2 (sin BC)
./ejecutar_experimentos.sh E4 3 30 192.168.1.53 # 3 runs distribuidos de E4
```

### Consolidación y Análisis Estadístico:
Para procesar todas las ejecuciones y regenerar el Cuadro III actualizado con los 3 runs:
```bash
python analizar_metricas.py
```
Este comando genera:
- `Metricas/consolidado/tabla_III_consolidada.csv`: Tabla con Mediana, Media, Desviación Estándar y Error Estándar ($SE$) agregados entre las 3 ejecuciones.
- `Metricas/consolidado/detalle_por_ejecucion.csv`: Desglose individual de cada una de las ejecuciones.

---

## 3. Pruebas de Verificación y Seguridad Criptográfica

Para validar experimentalmente la resistencia frente a ataques de manipulación:

### Prueba Rápida Automatizada (Standalone):
Ejecuta la batería de comprobaciones criptográficas directas (Caso Benigno, Servidor Malicioso y Cliente Malicioso):
```bash
./ejecutar_pruebas_verificacion.sh
# O directamente:
python test_verificacion.py
```

### Prueba Integrada con la Red Flower:
1. **Prueba 1 — Servidor Malicioso (Verificación Descendente)**:
   - El servidor altera los pesos en la ronda 2, enviando valores no correspondientes con el CID sellado.
   ```bash
   python server.py --exp TEST_ATK --run 1 --rounds 2 --simulate-attack tampered_server --attack-round 2
   python client.py --member 2 --exp TEST_ATK --run 1
   python client.py --member 3 --exp TEST_ATK --run 1
   ```
   *Resultado esperado*: En la ronda 2, los clientes detectan que los tensores descargados de IPFS no coinciden con los recibidos por gRPC, emiten una alerta explícita y **abortan el entrenamiento inmediatamente**.

2. **Prueba 2 — Cliente Malicioso (Verificación Ascendente)**:
   - El cliente 3 intenta enviar un CID fraudulento en la ronda 2 que no coincide con su registro en Besu.
   ```bash
   python server.py --exp TEST_ATK --run 2 --rounds 2
   python client.py --member 2 --exp TEST_ATK --run 2
   python client.py --member 3 --exp TEST_ATK --run 2 --simulate-attack tampered_client --attack-round 2
   ```
   *Resultado esperado*: En la ronda 2, el servidor consulta `getClientModel()` en Besu, detecta la discrepancia en el cliente 3, **descarta preventivamente su contribución** y ejecuta `FedAvg` exclusivamente con el cliente 2 legítimo.

