# Integración de Blockchain e IPFS para la Trazabilidad y Auditoría en el Aprendizaje Federado Vehicular

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Flower FL](https://img.shields.io/badge/Flower-FL-000000.svg)](https://flower.ai/)
[![Hyperledger Besu](https://img.shields.io/badge/Hyperledger-Besu-2F3134.svg)](https://www.hyperledger.org/projects/besu)
[![IPFS](https://img.shields.io/badge/IPFS-Kubo_v0.32.1-65C2CB.svg)](https://ipfs.tech/)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.20-363636.svg)](https://soliditylang.org/)

Repositorio oficial del framework híbrido de **Aprendizaje Federado (Flower)**, **Blockchain de Consorcio (Hyperledger Besu, IBFT 2.0)** y **Almacenamiento Distribuido Fuera de Cadena (IPFS)** para la auditoría, trazabilidad e integridad de modelos neuronales.

Este trabajo ha sido desarrollado en la **Escuela Politécnica Superior de la Universidad de Alicante (Departamento de Tecnología Informática y Computación)** por **David Piotr Znojek** bajo la tutoría de **Francisco A. Pujol López**.

---

## 📋 Resumen del Proyecto

El Aprendizaje Federado tradicional (*Federated Learning*) permite entrenar modelos colectivos preservando la privacidad de los datos locales, pero depende críticamente de un agregador central y carece de mecanismos nativos para auditar la legitimidad de las contribuciones locales, siendo vulnerable a ataques de envenenamiento (*model poisoning* o *server tampering*).

Esta arquitectura implementa un **protocolo de doble verificación criptográfica**:
1. **Almacenamiento fuera de cadena (*Off-Chain*)**: Los pesos neuronales binarios se suben a **IPFS Kubo**, obteniendo un identificador determinista de contenido (**CID**).
2. **Registro inmutable en cadena (*On-Chain*)**: Mediante un Smart Contract en Solidity (`FLRegistry.sol`) ejecutado sobre una red permisionada **Hyperledger Besu (IBFT 2.0)**, tanto el servidor central como los clientes firman y registran los CIDs de sus contribuciones por ronda.
3. **Auditoría cruzada en tiempo real**: 
   - **Verificación Descendente**: Los clientes cotejan el modelo global descargado frente al CID consolidado en Blockchain antes de entrenar (mitigando servidores comprometidos en $\sim 0{,}074$~s).
   - **Verificación Ascendente**: El servidor coteja las contribuciones recibidas frente a los CIDs firmados por los clientes en la EVM antes de ejecutar *FedAvg* (mitigando clientes envenenadores en $\sim 0{,}044$~s).

La sobrecarga temporal en red real es de tan solo el **9,5\%** (6,34~s por ronda), con un coste de gas estable y predecible por transacción que garantiza escalabilidad operativa e independencia del tamaño del modelo neuronal.

---

## 📂 Estructura del Repositorio

```text
Blockchain_ML/
├── Articulo/                    # Fuentes LaTeX del artículo científico y figuras
│   ├── main.tex                 # Documento principal (plantilla IEEE PES)
│   ├── main.pdf                 # Manuscrito compilado completo (15 páginas)
│   ├── secciones/               # Capítulos modulares del artículo
│   ├── figuras/                 # Gráficas, diagramas y evidencias de auditoría
│   └── rua.pdf                  # Memoria original del TFG
├── Dataset/                     # Conjunto de datos de eventos vehiculares
│   ├── traffic-images/          # 3.415 imágenes distribuidas en 4 clases
│   └── etiquetar.py             # Script de preparación y balanceo de datos
├── Metricas/                    # Telemetría experimental de 15 ejecuciones (450 rondas)
│   ├── E1/ a E5/                # Logs individuales por escenario y repetición
│   ├── Server/ y Client/        # Archivos CSV detallados de servidor y clientes
│   ├── Loss/                    # Convergencia de pérdida y precisión por ronda
│   └── consolidado/             # Métricas estadísticas agregadas
├── Redes_Blockchain/            # Redes Hyperledger Besu preconfiguradas
│   ├── 4_validadores/           # Quórum IBFT 2.0 base (f=1)
│   └── 7_validadores/           # Quórum IBFT 2.0 ampliado (f=2)
├── Scripts/                     # Scripts de ejecución, benchmarking y análisis
│   ├── server.py                # Servidor Flower con auditoría en Blockchain
│   ├── client.py                # Cliente Flower con verificación en IPFS y Besu
│   ├── server_sin_bc.py         # Servidor FL base sin Blockchain (baseline)
│   ├── client_sin_bc.py         # Cliente FL base sin Blockchain (baseline)
│   ├── contract_address.py      # Gestor de dirección y ABI de Smart Contracts
│   ├── test_verificacion.py     # Suite de validación de ataques adversariales
│   ├── generar_graficas_paper.py# Generador de figuras de alta resolución
│   └── README_EXPERIMENTACION.md# Protocolo detallado de pruebas
└── Smart_Contracts/             # Contratos inteligentes en Solidity
    ├── FLRegistry.sol           # Contrato de registro y doble verificación
    └── FLRegistry.json          # Bytecode y ABI compilada
```

---

## 🛠️ Requisitos Previos e Instalación

El entorno de pruebas ha sido desarrollado y validado sobre **Ubuntu 22.04 LTS (WSL2 / Linux)** y **Python 3.12**.

### 1. Actualización y Dependencias del Sistema
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git build-essential software-properties-common
```

### 2. Docker Engine y Docker Compose
```bash
# Repositorio oficial de Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalación de Docker y plugins
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Asignar permisos al usuario actual (reiniciar sesión tras ejecutar)
sudo usermod -aG docker $USER
```

### 3. IPFS Kubo (`v0.32.1`)
```bash
wget https://dist.ipfs.tech/kubo/v0.32.1/kubo_v0.32.1_linux-amd64.tar.gz
tar -xvzf kubo_v0.32.1_linux-amd64.tar.gz
cd kubo && sudo ./install.sh && cd ..
rm -rf kubo kubo_v0.32.1_linux-amd64.tar.gz

# Inicializar y configurar CORS para la API HTTP
ipfs init
ipfs config --json API.HTTPHeaders.Access-Control-Allow-Origin '["*"]'
ipfs config --json API.HTTPHeaders.Access-Control-Allow-Methods '["PUT", "GET", "POST"]'
```

### 4. Entorno de Python y Librerías
```bash
pip install torch torchvision flwr web3 pandas numpy matplotlib seaborn scipy requests
```

---

## 🚀 Guía de Puesta en Marcha Rápida

### Paso 1: Iniciar la Red Blockchain Besu (IBFT 2.0)
El repositorio incluye las redes preconfiguradas en `Redes_Blockchain/`. Para iniciar la red de 4 validadores:
```bash
cd Redes_Blockchain/4_validadores
./run.sh
```
*(Para detenerla en cualquier momento: `./stop.sh`)*.

Servicios desplegados automáticamente:
* **Nodo RPC Besu**: `http://localhost:8545`
* **Explorador de Bloques (Alethio / Quorum Explorer)**: `http://localhost:25000`
* **Monitorización (Grafana / Prometheus)**: `http://localhost:3000`

### Paso 2: Extraer la Dirección del Contrato Inteligente
En otra terminal, accede a la carpeta `Scripts/` y ejecuta:
```bash
cd Scripts
python contract_address.py
```
Este comando sincroniza la dirección de `FLRegistry.sol` en `Smart_Contracts/Contract_Data/FLRegistry_info.json`.

### Paso 3: Iniciar el Daemon de IPFS
```bash
ipfs daemon
```

### Paso 4: Ejecutar el Aprendizaje Federado con Trazabilidad
1. **Lanzar el Servidor Agregador**:
   ```bash
   cd Scripts
   python server.py --exp E1 --run 1 --rounds 30
   ```
2. **Lanzar los Clientes de Entrenamiento** (en terminales separadas o clientes remotos):
   ```bash
   # Cliente 2
   python client.py --member 2 --exp E1 --run 1
   
   # Cliente 3
   python client.py --member 3 --exp E1 --run 1
   ```

---

## 🛡️ Evaluación de Resiliencia y Ataques Adversariales

Para validar empíricamente la efectividad del protocolo frente a intentos de fraude sin esperar al ciclo completo de rondas:

```bash
cd Scripts
python test_verificacion.py
# O bien mediante el script automatizado:
./ejecutar_pruebas_verificacion.sh
```

El script simula de manera controlada dos vectores críticos de ataque:
* **Prueba 1 (Descendente - Servidor Malicioso)**: El servidor inyecta un modelo adulterado. El cliente coteja el CID recibido con el emitido en la Blockchain y aborta la ronda de forma preventiva en $\approx 0{,}074$~segundos.
* **Prueba 2 (Ascendente - Cliente Envenenador)**: Un cliente intenta colar gradientes manipulados con un hash no respaldado en la EVM. El agregador detecta la discrepancia on-chain y descarta la contribución en $\approx 0{,}044$~segundos.

> **Nota metodológica de seguridad:** La doble verificación criptográfica garantiza la detección determinista de ataques de adulteración física en tránsito (*tampering*) e inyección de modelos disidentes no respaldados on-chain. La mitigación de ataques semánticos donde los pesos han sido generados mediante manipulación de datos locales (*data poisoning*) y firmados legítimamente en la red requiere defensas complementarias de agregación bizantina (Krum, Median), contempladas en el trabajo futuro.

---

## 📊 Reproducción de Métricas y Gráficas del Artículo

Todas las métricas de las 15 ejecuciones y 450 rondas están registradas en la carpeta `Metricas/`. Para regenerar las tablas estadísticas y las figuras de alta resolución que ilustran el artículo:

```bash
cd Scripts
# Análisis numérico de medias, medianas, desviaciones y pruebas t-Student:
python analizar_metricas.py

# Generación automática de todas las figuras en formato PDF y PNG:
python generar_graficas_paper.py
```
Las figuras resultantes se exportan directamente a `Articulo/figuras/`.

---

## 📚 Dataset Vehicular CloudLab-AIA

El sistema entrena una red neuronal convolucional (**CNN**) sobre el conjunto de datos de eventos de tráfico de CloudLab-AIA, compuesto por **3.415 imágenes** etiquetadas en 4 categorías:
1. `accident`: 663 imágenes
2. `dense_traffic`: 778 imágenes
3. `sparse_traffic`: 947 imágenes
4. `weather`: 1.027 imágenes

---

## ✒️ Autores y Referencia

* **David Piotr Znojek** (`dawidznojek@gmail.com`) — Autor principal.
* **Francisco A. Pujol López** (`fpujol@ua.es`) — Tutor y coautor.

**Institución:** Escuela Politécnica Superior, Universidad de Alicante (España).  
**Artículo científico:** *Integración de Blockchain para la Trazabilidad y Auditoría en el Entrenamiento Distribuido de Modelos de Inteligencia Artificial* (Manuscrito disponible en [`Articulo/main.pdf`](Articulo/main.pdf)).

---

## 📄 Licencia

Este proyecto se distribuye bajo fines de investigación y docencia académica. Consulta los archivos individuales para licencias específicas de componentes de terceros (Flower, Hyperledger Besu, IPFS).
