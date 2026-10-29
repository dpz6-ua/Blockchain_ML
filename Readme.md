# Blockchain and IPFS Integration for Traceability and Auditing in Vehicular Federated Learning

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Flower FL](https://img.shields.io/badge/Flower-FL-000000.svg)](https://flower.ai/)
[![Hyperledger Besu](https://img.shields.io/badge/Hyperledger-Besu-2F3134.svg)](https://www.hyperledger.org/projects/besu)
[![IPFS](https://img.shields.io/badge/IPFS-Kubo_v0.32.1-65C2CB.svg)](https://ipfs.tech/)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.20-363636.svg)](https://soliditylang.org/)

Official repository of the hybrid framework combining **Federated Learning (Flower)**, **Consortium Blockchain (Hyperledger Besu, IBFT 2.0)**, and **Off-Chain Content-Addressable Storage (IPFS)** to provide end-to-end traceability, cryptographic integrity, and independent retrospective auditing in distributed deep learning.

This research has been conducted at the **Polytechnic University College of the University of Alicante (Department of Computer Technology and Computation)** by **David Piotr Znojek** under the supervision of **Francisco A. Pujol López**.

---

## 📋 Project Overview

Conventional Federated Learning (FL) collaboratively trains machine learning models while keeping raw data localized on edge devices. However, standard architectures rely unconditionally on a centralized aggregation coordinator and lack native mechanisms to audit the authenticity or fidelity of parameter updates, leaving the system vulnerable to coordinator equivocation (split-view attacks) and rogue parameter injections.

This framework introduces a **bidirectional cryptographic verification and retrospective auditing protocol**:

1. **Off-Chain Storage Plane**: Serialized binary weight tensors are stored in **IPFS**, yielding unique, content-derived multihash identifiers (**CIDs**).
2. **On-Chain Commitment Plane**: A Solidity smart contract (`FLRegistry.sol`) deployed on a permissioned **Hyperledger Besu (IBFT 2.0)** network immutably seals ECDSA-signed CIDs for both edge contributions and the global model each round.
3. **Runtime Cross-Verification**:
   - **Downward Verification (Client verifies Coordinator)**: Edge nodes query on-chain commitments via JSON-RPC, download the reference artifact from IPFS, and perform bit-by-bit tensor integrity checks before backpropagation (aborting within **149 ms** upon parameter mismatch).
   - **Upward Verification (Coordinator verifies Clients)**: The coordinator verifies that received memory weights match both the reported CID and the client's signed on-chain transaction before aggregation, discarding fraudulent or tampered updates within **31 ms**.
4. **Independent Ex-Post Auditing**: External regulators or participants can retrospectively query on-chain event logs and reconstruct canonical FedAvg aggregation directly from IPFS model artifacts, verifying exact mathematical fidelity ($\Delta = 0.000000$, CID equality) in **0.34 s** without accessing private edge training data.

Empirical evaluation over 15 complete executions (450 federated rounds) demonstrates a modest latency overhead of **9.5%** (+6.34 s per round in a physical multi-machine network), with strictly invariant EVM gas consumption per transaction (160,200 gas for client registrations; 169,649 gas for coordinator updates in steady state) completely decoupled from neural network parameter count.

---

## 📂 Repository Structure

```text
Blockchain_ML/
├── Articulo_Springer/           # Research manuscript sources (The Journal of Supercomputing, Springer Nature)
│   ├── main.tex                 # Main LaTeX document (Springer single-column sn-jnl template)
│   ├── main.pdf                 # Compiled manuscript PDF (38 pages)
│   ├── sections/                # Modular paper sections in English
│   ├── figures/                 # High-resolution vector diagrams and telemetry plots (300 DPI)
│   └── sn-bibliography.bib      # BibTeX citation database
├── Dataset/                     # Vehicular road hazard classification dataset (CloudLab-AIA)
│   ├── traffic-images/          # 3,415 road scenario images across 4 balanced classes
│   └── etiquetar.py             # Dataset preprocessing and partitioning utility
├── Metricas/                    # Experimental telemetry corpus (15 executions, 450 rounds)
│   ├── E1/ to E5/               # Granular execution logs by experimental configuration
│   ├── Server/ and Client/      # Detailed timing and network CSV telemetry
│   ├── Loss/                    # Round-by-round cross-entropy loss and accuracy metrics
│   └── consolidado/             # Aggregated statistical matrices and confidence intervals
├── Redes_Blockchain/            # Containerized Hyperledger Besu deployment templates
│   ├── 4_validadores/           # Baseline IBFT 2.0 consensus committee (f=1 Byzantine resilience)
│   └── 7_validadores/           # Expanded IBFT 2.0 consensus committee (f=2 Byzantine resilience)
├── Scripts/                     # Python orchestration, benchmarking, and auditing suite
│   ├── server.py                # Flower aggregation server with Besu & IPFS audit hooks
│   ├── client.py                # Flower edge client with bidirectional cross-verification
│   ├── server_sin_bc.py         # Baseline Flower server without blockchain layer
│   ├── client_sin_bc.py         # Baseline Flower client without blockchain layer
│   ├── contract_address.py      # Smart contract deployment address & ABI synchronizer
│   ├── test_verificacion.py     # Adversarial attack injection and mitigation test suite
│   ├── auditoria_expost.py      # Independent ex-post FedAvg reconstruction and audit tool
│   ├── generar_graficas_paper.py# High-resolution statistical visualization generator
│   └── README_EXPERIMENTACION.md# Detailed empirical benchmarking protocol
└── Smart_Contracts/             # Ethereum Virtual Machine (EVM) smart contracts
    ├── FLRegistry.sol           # Solidity smart contract with onlyServer access control
    └── FLRegistry.json          # Compiled bytecode and Application Binary Interface (ABI)
```

---

## 🛠️ Prerequisites and Installation

The evaluation testbed is validated on **Ubuntu 22.04 LTS (Linux / WSL2)** with **Python 3.12**.

### 1. System Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git build-essential software-properties-common
```

### 2. Docker Engine & Docker Compose
```bash
# Add official Docker repository
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker packages
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Grant non-root Docker permissions (reload shell session afterwards)
sudo usermod -aG docker $USER
```

### 3. IPFS Kubo (`v0.32.1`)
```bash
wget https://dist.ipfs.tech/kubo/v0.32.1/kubo_v0.32.1_linux-amd64.tar.gz
tar -xvzf kubo_v0.32.1_linux-amd64.tar.gz
cd kubo && sudo ./install.sh && cd ..
rm -rf kubo kubo_v0.32.1_linux-amd64.tar.gz

# Initialize IPFS node and configure CORS for API communication
ipfs init
ipfs config --json API.HTTPHeaders.Access-Control-Allow-Origin '["*"]'
ipfs config --json API.HTTPHeaders.Access-Control-Allow-Methods '["PUT", "GET", "POST"]'
```

### 4. Python Environment & Dependencies
```bash
pip install torch torchvision flwr web3 pandas numpy matplotlib seaborn scipy requests
```

---

## 🚀 Quick Start Guide

### Step 1: Start the Hyperledger Besu Network (IBFT 2.0)
Preconfigured deployment scripts are located in `Redes_Blockchain/`. To start the 4-validator committee:
```bash
cd Redes_Blockchain/4_validadores
./run.sh
```
*(To stop the network at any time: `./stop.sh`)*.

Automated endpoints:
* **Besu JSON-RPC Node**: `http://localhost:8545`
* **Block Explorer (Alethio / Quorum Explorer)**: `http://localhost:25000`
* **Telemetry Monitoring (Grafana / Prometheus)**: `http://localhost:3000`

### Step 2: Synchronize Contract Deployment Manifest
From the `Scripts/` directory:
```bash
cd Scripts
python contract_address.py
```
This utility deploys or verifies `FLRegistry.sol` and syncs the current address into `Smart_Contracts/Contract_Data/FLRegistry_info.json`.

### Step 3: Launch the IPFS Daemon
In a dedicated terminal:
```bash
ipfs daemon
```

### Step 4: Run Audited Federated Learning
1. **Launch the Aggregation Server**:
   ```bash
   cd Scripts
   python server.py --exp E1 --run 1 --rounds 30
   ```
2. **Launch Participating Edge Clients** (in separate terminals or networked workstations):
   ```bash
   # Edge Client 2
   python client.py --member 2 --exp E1 --run 1

   # Edge Client 3
   python client.py --member 3 --exp E1 --run 1
   ```

---

## 🛡️ Security Validation and Adversarial Tests

To empirically verify deterministic attack mitigation without waiting for a full 30-round training cycle:

```bash
cd Scripts
python test_verificacion.py
# Or via the automated shell harness:
./ejecutar_pruebas_verificacion.sh
```

The test harness evaluates the two primary threat vectors:
* **Test 1 (Downward Verification — Tampered Server vs. Client)**: The coordinator delivers candidate weights that deviate from the on-chain committed CID. The edge client detects the numerical discrepancy and aborts execution within **0.149 seconds**, protecting local data.
* **Test 2 (Upward Verification — Tampered Weights vs. Coordinator)**: A client transmits manipulated parameters or an unregistered CID. The coordinator identifies the mismatch against the on-chain commitment and discards the update from the FedAvg pool within **0.031 seconds**.

### Retrospective Ex-Post Auditing
To execute an autonomous forensic audit on committed rounds:
```bash
cd Scripts
python auditoria_expost.py --round 2
```
The tool queries `ModelUpdated` event logs in Besu, retrieves all participant CIDs, downloads model binary artifacts from IPFS, and reconstructs FedAvg in **0.34 seconds**, confirming exact mathematical fidelity ($\Delta = 0.000000$).

---

## 📊 Reproducing Paper Metrics and Figures

All runtime telemetry from the 450 experimental rounds is archived in `Metricas/`. To reproduce the statistical tables and high-resolution figures published in the paper:

```bash
cd Scripts
# Compute descriptive statistics, medians, and Welch's t-tests:
python analizar_metricas.py

# Generate all publication-quality vector plots (300 DPI):
python generar_graficas_paper.py
```
Generated plots are automatically deployed to `Articulo_Springer/figures/`.

---

## 📚 Vehicular Dataset (CloudLab-AIA)

The convolutional classifier (**CNN**) is trained on the CloudLab-AIA vehicular traffic event dataset, consisting of **3,415 images** across 4 balanced categories:
1. `accident`: 663 images
2. `dense_traffic`: 778 images
3. `sparse_traffic`: 947 images
4. `weather`: 1,027 images

---

## ✒️ Authors and Reference

* **David Piotr Znojek** (`dawidznojek@gmail.com` / `dpz6@alu.ua.es`) — Primary author.
* **Francisco A. Pujol López** (`fpujol@ua.es`) — Supervisor and coauthor.

**Affiliation:** Department of Computer Technology and Computation, Polytechnic University College, University of Alicante (Spain).  
**Scientific Manuscript:** *Decoupled Blockchain and IPFS Architecture for Scalable Traceability and Ex-Post Verifiability in Federated Learning* (Submitted to **The Journal of Supercomputing**, Springer Nature).  
* **LaTeX Source:** [`Articulo_Springer/main.tex`](Articulo_Springer/main.tex)
* **Compiled PDF:** [`Articulo_Springer/main.pdf`](Articulo_Springer/main.pdf)

---

## 📄 License

This repository is distributed for academic research and teaching purposes. Please refer to individual source headers for licenses of third-party software components (PyTorch, Flower, Hyperledger Besu, IPFS Kubo).
