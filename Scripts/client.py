import json
import pickle
import flwr as fl
import os
import requests
import torch
from web3 import Web3
from collections import OrderedDict
from torch import nn
import argparse
import numpy as np
from model import NetCliente, load_data
import csv
import time
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SMART_CONTRACTS_DIR = PROJECT_DIR / "Smart_Contracts"
METRICAS_DIR = PROJECT_DIR / "Metricas"
DATASET_PATH = PROJECT_DIR / "Dataset" / "traffic-images" / "dataset_etiquetado.csv"

CLIENT_ACCOUNTS = {
    2: {
        "address": Web3.to_checksum_address("0x627306090abaB3A6e1400e9345bC60c78a8BEf57"),
        "key": "0xc87509a1c067bbde78beb793e6fa76530b6382a4c0241e5e4a9ec0a0f44dc0d3"
    },
    3: {
        "address": Web3.to_checksum_address("0xf17f52151EbEF6C7334FAD080c5704D77216b732"),
        "key": "0xae6ae8e5ccbfb04590405997ee2d52d2b330726137b875053c36d94e974d162f"
    }
}

RPC_PORTS = {2: "20002", 3: "20004"}


class MiFlowerClient(fl.client.NumPyClient):
    def __init__(self, member_id, exp="E1", run=1, server_ip="localhost", simulate_attack="none", attack_round=2, train_data=None, test_data=None):
        self.member_id = member_id
        self.exp = exp
        self.run = run
        self.server_ip = server_ip
        self.simulate_attack = simulate_attack
        self.attack_round = attack_round

        self.model = NetCliente()
        self.train_data = train_data
        self.test_data = test_data

        # Conexión RPC a Besu
        eth_endpoint = f'http://{self.server_ip}:{RPC_PORTS.get(self.member_id, "20002")}'
        self.w3 = Web3(Web3.HTTPProvider(eth_endpoint))

        # Carga del contrato
        contract_info_path = SMART_CONTRACTS_DIR / "Contract_Data" / "FLRegistry_info.json"
        if not contract_info_path.exists():
            raise RuntimeError(f"No se encontró {contract_info_path}. Despliega primero el contrato.")
        with open(contract_info_path, "r") as f:
            contract_data = json.load(f)
        contract_address = Web3.to_checksum_address(contract_data.get('address'))

        with open(SMART_CONTRACTS_DIR / "FLRegistry.json", "r") as f:
            abi = json.load(f)

        self.contract = self.w3.eth.contract(address=contract_address, abi=abi)

        # Rutas de métricas
        self.dir_exp = METRICAS_DIR / self.exp / f"run_{self.run}"
        self.dir_exp.mkdir(parents=True, exist_ok=True)
        self.archivo_csv_exp = self.dir_exp / f"client_{self.member_id}.csv"

        self.dir_legacy = METRICAS_DIR / "Client"
        self.dir_legacy.mkdir(parents=True, exist_ok=True)
        self.archivo_csv_legacy = self.dir_legacy / f"metricas_client_{self.member_id}_{self.exp}_run{self.run}.csv"

        self.init_metricas_csv()

    def init_metricas_csv(self):
        header = [
            "ronda",
            "tiempo_total_cliente_seg",
            "tiempo_verif_desc_seg",
            "tiempo_entrenamiento_seg",
            "tiempo_subida_ipfs_seg",
            "tiempo_confirmacion_bc_seg",
            "gas_real",
            "estado",
            "timestamp"
        ]
        for path in [self.archivo_csv_exp, self.archivo_csv_legacy]:
            if not path.exists():
                with open(path, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)

    def guardar_metricas(self, ronda, t_total, t_verif, t_train, t_ipfs, t_tx, gas, estado):
        fila = [
            ronda,
            t_total,
            t_verif,
            t_train,
            t_ipfs,
            t_tx,
            gas,
            estado,
            time.time()
        ]
        for path in [self.archivo_csv_exp, self.archivo_csv_legacy]:
            with open(path, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(fila)

    def upload_to_ipfs(self, data):
        try:
            files = {'file': data}
            response = requests.post(f"http://{self.server_ip}:5001/api/v0/add?pin=false", files=files, timeout=15)
            if response.status_code == 200:
                return response.json()['Hash']
            else:
                print(f"[{self.member_id}] Error subiendo a IPFS: {response.text}")
                return None
        except Exception as e:
            print(f"[{self.member_id}] Error de conexión con IPFS: {e}")
            return None

    def register_on_blockchain(self, round_num, cid):
        account = CLIENT_ACCOUNTS[self.member_id]
        nonce = self.w3.eth.get_transaction_count(account["address"], 'pending')

        tx = self.contract.functions.registerClientModel(round_num, cid).build_transaction({
            'from': account["address"],
            'nonce': nonce,
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': self.w3.eth.chain_id
        })

        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=account["key"])
        start_time = time.time()
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        tiempo_confirmacion = time.time() - start_time

        gas_real = receipt.gasUsed
        print(f"[{self.member_id}] CID registrado en Blockchain ({cid}) en bloque {receipt.blockNumber} ({tiempo_confirmacion:.3f}s)")
        return gas_real, tiempo_confirmacion

    def get_last_model_hash_from_blockchain(self):
        try:
            last_model = self.contract.functions.getLastModel().call()
            return last_model[1]
        except Exception as e:
            print(f"[{self.member_id}] Error al obtener el CID desde la blockchain: {e}")
            return None

    def get_parameters(self, config):
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)

    def check_model_CID(self, blockchain_cid, parameters):
        if not blockchain_cid:
            return False
        
        # Si server_ip es localhost, usar 127.0.0.1 para evitar que el gateway de IPFS
        # intente redirigir por HTTP 301 a subdominios del tipo <CID>.ipfs.localhost
        ip_addr = "127.0.0.1" if self.server_ip in ["localhost", "127.0.0.1"] else self.server_ip

        try:
            # 1. Intentar descargar por la pasarela HTTP (puerto 8080)
            url = f"http://{ip_addr}:8080/ipfs/{blockchain_cid}"
            response = requests.get(url, timeout=15)

            # 2. Si la pasarela falla o redirige, usar directamente la API cat (puerto 5001)
            if response.status_code != 200:
                cat_url = f"http://{ip_addr}:5001/api/v0/cat?arg={blockchain_cid}"
                response = requests.post(cat_url, timeout=15)

            if response.status_code == 200:
                model_from_ipfs = pickle.loads(response.content)
                if not isinstance(model_from_ipfs, list):
                    model_from_ipfs = fl.common.parameters_to_ndarrays(model_from_ipfs)

                is_valid = all(
                    np.allclose(p_flower, p_ipfs, atol=1e-7)
                    for p_flower, p_ipfs in zip(parameters, model_from_ipfs)
                )
                return is_valid
            else:
                print(f"[{self.member_id}] Error al descargar modelo desde IPFS ({response.status_code})")
                return False
        except Exception as e:
            print(f"[{self.member_id}] Error de verificación con IPFS: {e}")
            return False

    def fit(self, parameters, config):
        start_fit = time.time()
        server_round = config.get("server_round", 1)

        if not isinstance(parameters, list):
            parameters = fl.common.parameters_to_ndarrays(parameters)

        # 1. Fase de Verificación Descendente (Cliente verifica Servidor)
        t_start_desc = time.time()
        last_model_CID = self.get_last_model_hash_from_blockchain()
        is_valid = self.check_model_CID(last_model_CID, parameters)
        t_verif_desc = time.time() - t_start_desc

        if not is_valid:
            t_total_abort = time.time() - start_fit
            print(f"\n{'!'*70}")
            print(f"[{self.member_id}] [ALERTA DE SEGURIDAD] El modelo recibido del servidor NO coincide con el CID registrado en Blockchain ({last_model_CID}).")
            print(f"[{self.member_id}] Verificación cruzada descendente FALLIDA. Abortando entrenamiento para proteger la privacidad local.")
            print(f"{'!'*70}\n")

            self.guardar_metricas(
                ronda=server_round,
                t_total=t_total_abort,
                t_verif=t_verif_desc,
                t_train=0.0,
                t_ipfs=0.0,
                t_tx=0.0,
                gas=0,
                estado="ABORTADO_POR_DISCREPANCIA"
            )
            return self.get_parameters(config={}), 0, {"error": "Invalid server model"}

        print(f"[{self.member_id}] Verificación descendente exitosa: Modelo verificado contra Blockchain e IPFS ({t_verif_desc:.3f}s)")
        print(f"[{self.member_id}] Iniciando entrenamiento local (3 épocas)")

        # 2. Fase de Entrenamiento Local
        t_start_train = time.time()
        self.set_parameters(parameters)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()

        self.model.train()
        for epoch in range(3):
            for images, labels in self.train_data:
                optimizer.zero_grad()
                outputs = self.model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
        t_train = time.time() - t_start_train

        new_params = self.get_parameters(config={})

        # 3. Fase de Subida a IPFS
        t_start_ipfs = time.time()
        params_bytes = pickle.dumps(new_params)
        my_cid = self.upload_to_ipfs(params_bytes)
        t_ipfs = time.time() - t_start_ipfs

        gas_used, t_confirm = 0, 0.0
        cid_a_reportar = my_cid

        if my_cid:
            # 4. Fase de Registro en Blockchain
            gas_used, t_confirm = self.register_on_blockchain(server_round, my_cid)

            # Inyección de ataque simulado del cliente si procede
            if self.simulate_attack == "tampered_client" and server_round == self.attack_round:
                print(f"\n{'='*70}")
                print(f"[{self.member_id}] [ATAQUE SIMULADO - CLIENTE] Enviando un CID adulterado no registrado on-chain al servidor")
                print(f"{'='*70}\n")
                cid_a_reportar = "QmTamperedHashFraudeQueNoCoincideConElRegistrado1234"

            t_total = time.time() - start_fit
            self.guardar_metricas(
                ronda=server_round,
                t_total=t_total,
                t_verif=t_verif_desc,
                t_train=t_train,
                t_ipfs=t_ipfs,
                t_tx=t_confirm,
                gas=gas_used,
                estado="EXITOSO"
            )

            num_ejemplos = len(self.train_data.dataset) if self.train_data else 1
            return new_params, num_ejemplos, {
                "cid": cid_a_reportar,
                "address": CLIENT_ACCOUNTS[self.member_id]["address"]
            }

        t_total_err = time.time() - start_fit
        self.guardar_metricas(
            ronda=server_round,
            t_total=t_total_err,
            t_verif=t_verif_desc,
            t_train=t_train,
            t_ipfs=t_ipfs,
            t_tx=0.0,
            gas=0,
            estado="ERROR_IPFS"
        )
        return new_params, 1, {}

    def evaluate(self, parameters, config):
        self.set_parameters(parameters)
        criterion = nn.CrossEntropyLoss()
        correct, loss = 0, 0.0

        self.model.eval()
        with torch.no_grad():
            for images, labels in self.test_data:
                outputs = self.model(images)
                loss += criterion(outputs, labels).item()
                correct += (torch.max(outputs, 1)[1] == labels).sum().item()

        accuracy = correct / len(self.test_data.dataset)
        return float(loss) / len(self.test_data), len(self.test_data.dataset), {"accuracy": accuracy}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente Flower con Hyperledger Besu e IPFS")
    parser.add_argument("--member", type=int, choices=[2, 3], required=True, help="ID del miembro (2 o 3)")
    parser.add_argument("--exp", type=str, default="E1", help="ID del experimento (E1, E4, E5)")
    parser.add_argument("--run", type=int, default=1, help="Número de ejecución (1, 2, 3)")
    parser.add_argument("--server-ip", type=str, default="localhost", help="IP del servidor Flower / IPFS")
    parser.add_argument("--server-port", type=str, default="8081", help="Puerto gRPC de Flower")
    parser.add_argument("--simulate-attack", type=str, choices=["none", "tampered_client"], default="none",
                        help="Simular cliente enviando CID fraudulento al servidor")
    parser.add_argument("--attack-round", type=int, default=2, help="Ronda en la que se inyecta el ataque")
    args = parser.parse_args()

    print(f"Iniciando Cliente {args.member} - Exp: {args.exp}, Run: {args.run}, Servidor: {args.server_ip}:{args.server_port}")
    if args.simulate_attack != "none":
        print(f"MODO DE ATAQUE ACTIVO: {args.simulate_attack} en ronda {args.attack_round}")

    train_data, test_data = load_data(str(DATASET_PATH))

    client = MiFlowerClient(
        member_id=args.member,
        exp=args.exp,
        run=args.run,
        server_ip=args.server_ip,
        simulate_attack=args.simulate_attack,
        attack_round=args.attack_round,
        train_data=train_data,
        test_data=test_data
    )

    fl.client.start_client(
        server_address=f"{args.server_ip}:{args.server_port}",
        client=client.to_client()
    )