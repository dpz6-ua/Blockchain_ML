import json
import pickle
import flwr as fl
import os
import requests
import torch
from web3 import Web3
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
from collections import OrderedDict
from torch import nn
import argparse
import numpy as np
from model import NetCliente, load_data
import csv
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--member", type=int, choices=[2, 3], required=True, help="ID del miembro")
args = parser.parse_args()

RPC_PORTS = {2: "20002", 3: "20004"}
SERVER_ADDRESS = "localhost"  #192.168.1.53 en el otro ordenador
ETH_ENDPOINT = f'http://{SERVER_ADDRESS}:{RPC_PORTS[args.member]}'

# carga de datos del contrato y ABI
with open("../Smart_Contracts/Contract_Data/FLRegistry_info.json", "r") as f:
    contract_data = json.load(f)
FLaddress = contract_data.get('address')
print(f"Dirección del contrato obtenida: {FLaddress}")
CONTRACT_ADDRESS = Web3.to_checksum_address(FLaddress)

with open("../Smart_Contracts/FLRegistry.json", "r") as f:
    ABI = json.load(f)

# las claves deberían sacarse de los ficheros. de momento hardcoded
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

class MiFlowerClient(fl.client.NumPyClient):
    def __init__(self, train_data, test_data):
        self.model = NetCliente()
        self.w3 = Web3(Web3.HTTPProvider(ETH_ENDPOINT))
        self.contract = self.w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)
        self.train_data = train_data
        self.test_data = test_data
        
        self.metricas_path = Path("../Metricas/Client/")
        self.metricas_path.mkdir(parents=True, exist_ok=True)
        self.csv_file = self.metricas_path / f"metricas_client_{args.member}_bchain_7vals.csv"
        self.init_metricas_csv()
      
    def init_metricas_csv(self):
        if not self.csv_file.exists():
            with open(self.csv_file, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ronda", "gas_real", "tiempo_confirmacion", "tiempo_total_con_commit", "timestamp"
                ])

    def guardar_metricas(self, num_ronda, gas_real, tiempo_confirmacion, tiempo_total):
        with open(self.csv_file, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                num_ronda, gas_real, tiempo_confirmacion, tiempo_total, time.time()
            ])         
      
    def upload_to_ipfs(self, data):
        try:
            files = {'file': data}
            response = requests.post(f"http://{SERVER_ADDRESS}:5001/api/v0/add", files=files)
            return response.json()['Hash']
        except Exception as e:
            print(f"Error subiendo a IPFS: {e}")
            return None
        
    def register_on_blockchain(self, round_num, cid):
        account = CLIENT_ACCOUNTS[args.member]
        nonce = self.w3.eth.get_transaction_count(account["address"])
        
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
        end_time = time.time()
        
        tiempo_confirmacion = end_time - start_time
        gas_real = receipt.gasUsed
        print(f"[{args.member}] Hash registrado en Blockchain: {cid}")
        return gas_real, tiempo_confirmacion

    def get_last_model_hash_from_blockchain(self):
        try:
            last_model = self.contract.functions.getLastModel().call()
            return last_model[1]
        except Exception as e:
            print(f"Error al obtener el modelo desde la blockchain: {e}")
            return None
         
    def get_parameters(self, config):
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)
        
    def check_model_CID(self, blockchain_cid, parameters):
        try:
            response = requests.get(f"http://{SERVER_ADDRESS}:8080/ipfs/{blockchain_cid}", timeout=10)
            if response.status_code == 200:
                model_from_ipfs = pickle.loads(response.content)
                try:
                    if not isinstance(model_from_ipfs, list):
                        model_from_ipfs = fl.common.parameters_to_ndarrays(model_from_ipfs)
                        
                    is_valid = all(
                        np.allclose(p_flower, p_ipfs, atol=1e-7) 
                        for p_flower, p_ipfs in zip(parameters, model_from_ipfs)
                    )
                    return is_valid
                except Exception as e:
                    print(f"Error en la comparación: {e}")
                    return False
            else:
                print(f"Error al descargar el modelo desde IPFS: {response.text}")
                return False
        except Exception as e:
            print(f"Error de conexión con IPFS: {e}")
            return False

    def fit(self, parameters, config):
        start_fit = time.time()
        if not isinstance(parameters, list):
            parameters = fl.common.parameters_to_ndarrays(parameters)
            
        last_model_CID = self.get_last_model_hash_from_blockchain()
        
        if not self.check_model_CID(last_model_CID, parameters):
            print(f"[{args.member}] El modelo del servidor es corrupto. Abortando")
            return self.get_parameters(config={}), 0, {"error": "Invalid server model"}

        print(f"[{args.member}] Modelo del servidor correcto")
        print(f"[{args.member}] Iniciando entrenamiento local")
        
        self.set_parameters(parameters)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()
        
        self.model.train()
        for epoch in range(3):
            print(epoch)
            for images, labels in self.train_data:
                optimizer.zero_grad()
                outputs = self.model(images)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
        
        new_params = self.get_parameters(config={})
        params_bytes = pickle.dumps(new_params)
        my_cid = self.upload_to_ipfs(params_bytes)
        
        gas_used, t_confirm = 0, 0
        if my_cid:
            server_round = config.get("server_round", 1)
            gas_real, t_confirm = self.register_on_blockchain(server_round, my_cid)
            
            total_time = time.time() - start_fit
            self.guardar_metricas(server_round, gas_real, t_confirm, total_time)
            
            return new_params, 1, {
                "cid": my_cid, 
                "address": CLIENT_ACCOUNTS[args.member]["address"]
            }
        
        return new_params, 1, {}

    def evaluate(self, parameters, config):
        print(f"[{args.member}] Evaluando modelo")
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
        print(f"[{args.member}] Accuracy: {accuracy:.4f}")
        return float(loss) / len(self.test_data), len(self.test_data.dataset), {"accuracy": accuracy}

if __name__ == "__main__":
    print(f"Conectando Cliente Member {args.member} al servidor Flower ({SERVER_ADDRESS}:8081)")
    train_data, test_data = load_data("../Dataset/traffic-images/dataset_etiquetado.csv")
    
    fl.client.start_client(
        server_address=f"{SERVER_ADDRESS}:8081", 
        client=MiFlowerClient(train_data, test_data).to_client()
    )