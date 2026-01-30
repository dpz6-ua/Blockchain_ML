import flwr as fl
from web3 import Web3
import json
import pickle
import requests
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import torch
import torch.nn as nn

ETH_ENDPOINT = 'http://localhost:18545'
CONTRACT_ADDRESS = Web3.to_checksum_address("0x42699A7612A82f1d9C36148af9C77354759b210b")
MEMBER1_ADDRESS = Web3.to_checksum_address("0xfe3b557e8fb62b89f4916b721be55ceb828dbd73")
PRIV_KEY1 = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
IPFS_API_URL = "http://127.0.0.1:5001/api/v0/add"

with open("../Smart_Contracts/FLRegistry.json", "r") as f:
    ABI = json.load(f)

class NetCliente(nn.Module):
    def __init__(self):
        super(NetCliente, self).__init__()
        self.fc = nn.Linear(10, 2)
    def forward(self, x):
        return self.fc(x)

class MiBesuServer(fl.server.strategy.FedAvg):
    def __init__(self, **kwargs):
        
        modelo_init = NetCliente()
        pesos_iniciales = [val.cpu().numpy() for _, val in modelo_init.state_dict().items()]
        
        self.w3 = Web3(Web3.HTTPProvider(ETH_ENDPOINT))
        self.contract = self.w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)
        
        pesos = pickle.dumps(pesos_iniciales)
        model_cid = self.upload_to_ipfs(pesos)
        
        if model_cid is None:
            print("No se pudo subir el modelo inicial a IPFS")
        else:
            print(f"Modelo inicial guardado en IPFS con CID: {model_cid}") 
            self.send_transaction(0, model_cid)
        
        super().__init__(
            initial_parameters=fl.common.ndarrays_to_parameters(pesos_iniciales), 
            **kwargs
        )        

    def upload_to_ipfs(self, data_bytes):
        try:
            files = {'file': data_bytes}
            response = requests.post(IPFS_API_URL, files=files)
            if response.status_code == 200:
                return response.json()['Hash']
            else:
                print(f"Error en IPFS: {response.text}")
                return None
        except Exception as e:
            print(f"Error de conexión con IPFS: {e}")
            return None
    
    def aggregate_fit(self, server_round, results, failures):
        agg_params, agg_metrics = super().aggregate_fit(server_round, results, failures)
        
        if agg_params is not None:
            print(f"Finalizando ronda: {server_round}")
            
            pesos = pickle.dumps(agg_params)
            model_cid = self.upload_to_ipfs(pesos)
            if model_cid is None:
                print("No se pudo subir el modelo a IPFS")
                return agg_params, agg_metrics
            
            print(f"Modelo guardado en IPFS con CID: {model_cid}")
            self.send_transaction(server_round, model_cid)
        
        return agg_params, agg_metrics
    
    def send_transaction(self, round_id, model_cid):
        try:
            nonce = self.w3.eth.get_transaction_count(MEMBER1_ADDRESS)
            tx = self.contract.functions.updateModel(round_id, model_cid).build_transaction({
                'from': MEMBER1_ADDRESS,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.w3.eth.chain_id
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=PRIV_KEY1)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"Transacción enviada: {tx_hash.hex()}")
            self.w3.eth.wait_for_transaction_receipt(tx_hash)
            print("Transacción confirmada en la blockchain")
            
        except Exception as e:
            print(f"Error al guardar el modelo en el contrato: {e}")  
       
if __name__ == "__main__":
    server_strat = MiBesuServer(min_fit_clients=2, min_available_clients=2)
    print("Servidor en marcha")
    fl.server.start_server(
        server_address="0.0.0.0:8081",
        config=fl.server.ServerConfig(num_rounds=3),
        strategy=server_strat
    )