import time
import csv
import flwr as fl
from web3 import Web3
import json
import pickle
import requests
import os
from model import NetCliente
from pathlib import Path
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

with open("../Smart_Contracts/Contract_Data/FLRegistry_info.json", "r") as f:
    contract_data = json.load(f)
FLaddress = contract_data.get('address')
CONTRACT_ADDRESS = Web3.to_checksum_address(FLaddress)

ETH_ENDPOINT = 'http://localhost:18545'
MEMBER1_ADDRESS = Web3.to_checksum_address("0xfe3b557e8fb62b89f4916b721be55ceb828dbd73")
PRIV_KEY1 = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
IPFS_API_URL = "http://127.0.0.1:5001/api/v0/add"

with open("../Smart_Contracts/FLRegistry.json", "r") as f:
    ABI = json.load(f)

class MiBesuServer(fl.server.strategy.FedAvg):
    def __init__(self, **kwargs):
        
        modelo_init = NetCliente()
        pesos_iniciales = [val.cpu().numpy() for _, val in modelo_init.state_dict().items()]
        self.tiempo_init_ronda = 0
        
        self.w3 = Web3(Web3.HTTPProvider(ETH_ENDPOINT))
        self.contract = self.w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)
        
        pesos = pickle.dumps(pesos_iniciales)
        model_cid = self.upload_to_ipfs(pesos)
        
        if model_cid is None:
            print("No se pudo subir el modelo inicial a IPFS")
        else:
            print(f"Modelo inicial guardado en IPFS con CID: {model_cid}") 
            self.send_transaction(0, model_cid)
            
        self.path_metricas = Path("../Metricas/Server/")
        self.path_metricas.mkdir(parents=True, exist_ok=True)
        self.archivo_csv = self.path_metricas / "metricas_server_bchain_7vals.csv"
        self.init_metricas_csv()
        
        super().__init__(
            initial_parameters=fl.common.ndarrays_to_parameters(pesos_iniciales), 
            **kwargs
        )        

    def init_metricas_csv(self):
        if not self.archivo_csv.exists():
            with open(self.archivo_csv, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ronda", 
                    "gas_consumido", 
                    "tiempo_confirmacion_seg", 
                    "tiempo_total_ronda_seg",
                    "timestamp"
                ])

    def guardar_metricas(self, num_ronda, gas, tiempo_confirmacion, tiempo_ronda_total):
        with open(self.archivo_csv, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                num_ronda, 
                gas, 
                tiempo_confirmacion, 
                tiempo_ronda_total,
                time.time()
            ])

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
        if not results:
            return None, {}

        valid_results = []
        self.tiempo_init_ronda = time.time()
        
        for client_proxy, fit_res in results:
            client_cid = fit_res.metrics.get("cid")
            client_address = fit_res.metrics.get("address")
            
            if not client_cid or not client_address:
                print(f"Rechazando cliente {client_proxy.cid}")
                continue

            try:
                blockchain_cid = self.contract.functions.getClientModel(
                    server_round, 
                    Web3.to_checksum_address(client_address)
                ).call()

                if blockchain_cid == client_cid:
                    print(f"Verificación exitosa para {client_address}")
                    valid_results.append((client_proxy, fit_res))
                else:
                    print(f"CUIDADO: CID de {client_address} no coincide con Blockchain.")
            except Exception as e:
                print(f"Error validando cliente en blockchain: {e}")

        agg_params, agg_metrics = super().aggregate_fit(server_round, valid_results, failures)
        
        if agg_params is not None:
            pesos = pickle.dumps(fl.common.parameters_to_ndarrays(agg_params))
            model_cid = self.upload_to_ipfs(pesos)
            
            if model_cid:
                tiempo_fin_ronda = time.time() - self.tiempo_init_ronda  # tiempo de fin de ronda
                print(f"Modelo global ronda {server_round} registrado: {model_cid}")
                gas_consumido, tiempo_transaccion = self.send_transaction(server_round, model_cid)
                self.guardar_metricas(server_round, gas_consumido, tiempo_transaccion, tiempo_fin_ronda)
                
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
            
            tiempo_start_transaccion = time.time()
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"Transacción enviada: {tx_hash.hex()}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            tiempo_end_transaccion = time.time() - tiempo_start_transaccion
            gas_real_consumido = receipt.gasUsed
            
            print("Transacción confirmada en la blockchain")
            
            return gas_real_consumido, tiempo_end_transaccion
            
        except Exception as e:
            print(f"Error al guardar el modelo en el contrato: {e}")  
            return 0, 0
       
def fit_config(server_round: int):
    return {"server_round": server_round}
       
if __name__ == "__main__":
    server_strat = MiBesuServer(min_fit_clients=2, min_available_clients=2, on_fit_config_fn=fit_config,)
    print("Servidor en marcha")
    fl.server.start_server(
        server_address="0.0.0.0:8081",
        config=fl.server.ServerConfig(num_rounds=30),
        strategy=server_strat
    )