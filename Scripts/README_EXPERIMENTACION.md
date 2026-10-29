# Comprehensive Experimental Benchmarking Protocol: Blockchain + Federated Learning + IPFS

This technical guide details the execution, telemetry measurement methodology, statistical aggregation, and security validation protocols supporting the research paper:

> **"Integrating Blockchain and IPFS for Traceability, Integrity, and Ex-Post Auditing in Federated Learning"**  
> *Submitted to The Journal of Supercomputing, Springer Nature.*  
> Manuscript: [`../Articulo_Springer/main.tex`](../Articulo_Springer/main.tex) | [`../Articulo_Springer/main.pdf`](../Articulo_Springer/main.pdf)

---

## 1. Experimental Telemetry and Round Timing Methodology

### Discrepancy Identified in Historical Baseline Measurements:
- In earlier preliminary benchmarks (historical Table 3 / Table III), metrics measured solely the time that each client spent inside its local `fit()` execution loop (*E1: 89.37 s, E2: 84.15 s, E3: 64.26 s, E4: 71.29 s, E5: 70.88 s*).
- Under the blockchain-enabled architecture (`client.py`), this local client loop accounted for downward verification from IPFS, local PyTorch training (3 epochs), artifact upload to IPFS, and ECDSA-signed on-chain transaction confirmation (`registerClientModel`) on Hyperledger Besu.
- In the baseline without blockchain (`client_sin_bc.py`), it recorded only local model training.
- Consequently, **the coordinator's final block confirmation transaction (`updateModel`, taking between 4.8 s and 6.9 s) was excluded** from the client-reported round duration, even though end-to-end round definitions include coordinator commitment.

### Standardized Two-Tier Measurement Architecture:
All orchestration scripts implement symmetric, rigorous telemetry logging across two complementary tiers:

#### 1. Coordinator Tier (End-to-End Round Duration):
- Measured from the dispatch of round parameters in `configure_fit` to the completion of canonical FedAvg aggregation and final block confirmation of `updateModel` in `aggregate_fit`.
- Captured fields in `server.csv`:
  - `tiempo_total_ronda_seg`: True end-to-end wall-clock duration of the complete federated round.
  - `tiempo_espera_clientes_seg`: Aggregated client communication, training, and local commitment latency.
  - `tiempo_verif_clientes_seg`: On-chain verification latency for participant CIDs on Besu (`getClientModel`).
  - `tiempo_agregacion_fedavg_seg`: Computational execution time of canonical FedAvg aggregation.
  - `tiempo_subida_ipfs_seg`: Model serialization and upload time of $w^{(t+1)}$ to IPFS.
  - `tiempo_confirmacion_tx_seg`: Block inclusion and receipt latency of `updateModel` under IBFT 2.0 consensus.
  - `gas_consumido`: Exact EVM gas consumed by the coordinator transaction.
  - `clientes_validos` / `clientes_descartados`: Number of validated vs. rejected client contributions.

#### 2. Client Tier (Local Training Cycle and Phase Breakdown):
- Captured fields in `client_X.csv`:
  - `tiempo_total_cliente_seg`: Total client execution loop (retaining direct historical comparability with Table 3).
  - `tiempo_verif_desc_seg`: On-chain JSON-RPC query + IPFS model retrieval + bit-by-bit tensor integrity audit (0 in baseline without BC).
  - `tiempo_entrenamiento_seg`: Pure PyTorch backpropagation and optimization (identical across both architectures).
  - `tiempo_subida_ipfs_seg`: Model serialization and IPFS upload (0 in baseline without BC).
  - `tiempo_confirmacion_bc_seg`: ECDSA-signed `registerClientModel` transaction confirmation (0 in baseline without BC).
  - `gas_real`: Exact EVM gas consumed by the client registration transaction.
  - `estado`: `EXITOSO` (successful) or `ABORTADO_POR_DISCREPANCIA` (aborted due to tensor discrepancy).

---

## 2. Experimental Execution Protocol (3 Independent Runs per Setup)

To ensure statistical significance and provide robust confidence intervals, all 5 experimental configurations (E1 to E5) are evaluated across 3 independent executions (30 rounds each, totaling 450 rounds):

### Manual Terminal Execution:
```bash
# Example: Configuration E1 (Single-host, Blockchain-enabled, 4 validators), Run 1
python contract_address.py
python server.py --exp E1 --run 1 --rounds 30
python client.py --member 2 --exp E1 --run 1
python client.py --member 3 --exp E1 --run 1

# Run 2 of Configuration E1 (with freshly redeployed contract):
python contract_address.py
python server.py --exp E1 --run 2 --rounds 30
python client.py --member 2 --exp E1 --run 2
python client.py --member 3 --exp E1 --run 2
```

### Automated Multi-Run Harness:
The `ejecutar_experimentos.sh` shell harness orchestrates consecutive runs automatically, ensuring contract redeployment between runs to prevent state collision:
```bash
./ejecutar_experimentos.sh <EXP_ID> <NUM_RUNS> <NUM_ROUNDS> [SERVER_IP]

# Examples:
./ejecutar_experimentos.sh E1 3 30 localhost     # 3 complete runs of E1 (Single-host, 4 validators)
./ejecutar_experimentos.sh E2 3 30 localhost     # 3 complete runs of E2 (Baseline without BC)
./ejecutar_experimentos.sh E3 3 30 localhost     # 3 complete runs of E3 (Single-host, 7 validators)
./ejecutar_experimentos.sh E4 3 30 192.168.1.53  # 3 complete runs of E4 (Distributed, 4 validators)
./ejecutar_experimentos.sh E5 3 30 192.168.1.53  # 3 complete runs of E5 (Distributed without BC)
```

### Statistical Aggregation and Paper Metrics:
To consolidate raw CSV telemetry across all 15 executions and regenerate Table 3:
```bash
python analizar_metricas.py
```
This utility generates:
- `Metricas/consolidado/tabla_III_consolidada.csv`: Aggregated matrix detailing Median, Mean, Sample Standard Deviation ($s$), and Standard Error ($SE = s / \sqrt{n}$) across all runs.
- `Metricas/consolidado/detalle_por_ejecucion.csv`: Granular per-run and per-round statistical breakdown.

---

## 3. Cryptographic Verification and Adversarial Security Tests

To validate deterministic mitigation of parameter manipulation and integrity violations without awaiting a full 30-round convergence cycle:

### Standalone Automated Test Suite:
Executes the self-contained cryptographic audit test bench (evaluating benign execution, manipulated server parameters, and manipulated client parameters):
```bash
./ejecutar_pruebas_verificacion.sh
# Or directly:
python test_verificacion.py
```

### Integrated In-Flight Threat Scenarios with Flower:

#### Test 1 — Manipulated Server Parameters (Downward Verification):
- The coordinator deliberately alters weight tensors in round 2, transmitting parameters that do not correspond to the on-chain committed CID:
  ```bash
  python server.py --exp TEST_ATK --run 1 --rounds 2 --simulate-attack tampered_server --attack-round 2
  python client.py --member 2 --exp TEST_ATK --run 1
  python client.py --member 3 --exp TEST_ATK --run 1
  ```
  *Expected Behavior*: In round 2, edge clients verify candidate weights against the immutable on-chain CID from Besu and the IPFS reference artifact, detect the tensor mismatch within **0.149 s**, raise an explicit integrity alert, and **immediately abort training**, preventing compromised parameters from contaminating edge models.

#### Test 2 — Manipulated Client Weights or Fraudulent CID (Upward Verification):
- Client 3 transmits manipulated parameters or reports a fraudulent CID in round 2 that deviates from its ECDSA-signed on-chain transaction:
  ```bash
  python server.py --exp TEST_ATK --run 2 --rounds 2
  python client.py --member 2 --exp TEST_ATK --run 2
  python client.py --member 3 --exp TEST_ATK --run 2 --simulate-attack tampered_client --attack-round 2
  ```
  *Expected Behavior*: In round 2, the aggregation coordinator queries `getClientModel()` on Besu, verifies triple equality ($\text{CID}_{\text{calc}} == \text{CID}_{\text{gRPC}} == \text{CID}_{\text{onchain}}$), identifies the discrepancy within **0.031 s**, **discards the untrusted contribution from the round**, and computes `FedAvg` exclusively over legitimate client updates.

---

## 4. Retrospective Ex-Post Auditing

To independently reconstruct and cryptographically verify the mathematical fidelity of any past federated round:
```bash
python auditoria_expost.py --round 2
```
This tool independently:
1. Queries historical `ModelUpdated` event logs emitted by `FLRegistry.sol` on Hyperledger Besu.
2. Extracts participating client addresses and their respective immutable IPFS CIDs.
3. Retrieves the exact binary weight tensors from IPFS.
4. Executes canonical FedAvg aggregation and computes the cryptographic digest of the reconstructed model.
5. Verifies bit-by-bit numerical equality ($\Delta = 0.000000$) and multihash identity against the coordinator's committed round model in **0.34 s**, providing unforgeable regulatory proof without disclosing private training datasets.
