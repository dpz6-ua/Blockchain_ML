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

parser = argparse.ArgumentParser()
parser.add_argument("--member", type=int, choices=[2, 3], required=True, help="ID del miembro")
args = parser.parse_args()

RPC_PORTS = {2: "20002", 3: "20004"}
ETH_ENDPOINT = f'http://localhost:{RPC_PORTS[args.member]}'

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
        
    def upload_to_ipfs(self, data):
        try:
            files = {'file': data}
            response = requests.post("http://127.0.0.1:5001/api/v0/add", files=files)
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
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        self.w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"[{args.member}] Hash registrado en Blockchain: {cid}")

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
            response = requests.get(f"http://127.0.0.1:8080/ipfs/{blockchain_cid}", timeout=10)
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
        if not isinstance(parameters, list):
            parameters = fl.common.parameters_to_ndarrays(parameters)
            
        last_model_CID = self.get_last_model_hash_from_blockchain()
        
        if not self.check_model_CID(last_model_CID, parameters):
            print(f"[{args.member}] El modelo del servidor es corrupto. Abortando")
            return self.get_parameters(config={}), 0, {"error": "Invalid server model"}

        print(f"[{args.member}] Modelo del servidor correcto")
        print(f"[{args.member}] Iniciando entrenamiento local")
        
        # ... código de entrenamiento ...
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
        
        if my_cid:
            server_round = config.get("server_round", 1)
            self.register_on_blockchain(server_round, my_cid)
            
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
    print(f"Conectando Cliente Member {args.member} al servidor Flower (0.0.0.0:8081)")
    train_data, test_data = load_data("../Dataset/traffic-images/dataset_etiquetado.csv")
    
    fl.client.start_client(
        server_address="127.0.0.1:8081", 
        client=MiFlowerClient(train_data, test_data).to_client()
    )