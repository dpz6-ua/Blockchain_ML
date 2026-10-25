import time
import csv
import flwr as fl
from web3 import Web3
import json
import pickle
import requests
import os
import argparse
from pathlib import Path
from model import NetCliente

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SMART_CONTRACTS_DIR = PROJECT_DIR / "Smart_Contracts"
METRICAS_DIR = PROJECT_DIR / "Metricas"

contract_info_path = SMART_CONTRACTS_DIR / "Contract_Data" / "FLRegistry_info.json"
if contract_info_path.exists():
    with open(contract_info_path, "r") as f:
        contract_data = json.load(f)
    FLaddress = contract_data.get('address')
    CONTRACT_ADDRESS = Web3.to_checksum_address(FLaddress) if FLaddress else None
else:
    CONTRACT_ADDRESS = None

abi_path = SMART_CONTRACTS_DIR / "FLRegistry.json"
if abi_path.exists():
    with open(abi_path, "r") as f:
        ABI = json.load(f)
else:
    ABI = None

ETH_ENDPOINT = 'http://127.0.0.1:18545'
MEMBER1_ADDRESS = Web3.to_checksum_address("0xfe3b557e8fb62b89f4916b721be55ceb828dbd73")
PRIV_KEY1 = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
IPFS_API_URL = "http://127.0.0.1:5001/api/v0/add?pin=false"


class MiBesuServer(fl.server.strategy.FedAvg):
    def __init__(self, exp="E1", run=1, simulate_attack="none", attack_round=2, **kwargs):
        self.exp = exp
        self.run = run
        self.simulate_attack = simulate_attack
        self.attack_round = attack_round
        self.tiempo_inicio_ronda = 0.0

        if CONTRACT_ADDRESS is None or ABI is None:
            raise RuntimeError("Información del contrato no encontrada. Despliega primero con contract_address.py")

        self.w3 = Web3(Web3.HTTPProvider(ETH_ENDPOINT))
        self.contract = self.w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)

        modelo_init = NetCliente()
        pesos_iniciales = [val.cpu().numpy() for _, val in modelo_init.state_dict().items()]

        pesos = pickle.dumps(pesos_iniciales)
        model_cid = self.upload_to_ipfs(pesos)

        if model_cid is None:
            print("AVISO: No se pudo subir el modelo inicial a IPFS (¿daemon no iniciado?)")
        else:
            print(f"Modelo inicial guardado en IPFS con CID: {model_cid}")
            self.send_transaction(0, model_cid)

        # Configuración de rutas de métricas
        self.dir_exp = METRICAS_DIR / self.exp / f"run_{self.run}"
        self.dir_exp.mkdir(parents=True, exist_ok=True)
        self.archivo_csv_exp = self.dir_exp / "server.csv"

        self.dir_legacy = METRICAS_DIR / "Server"
        self.dir_legacy.mkdir(parents=True, exist_ok=True)
        self.archivo_csv_legacy = self.dir_legacy / f"metricas_server_{self.exp}_run{self.run}.csv"

        self.init_metricas_csv()

        super().__init__(
            initial_parameters=fl.common.ndarrays_to_parameters(pesos_iniciales),
            **kwargs
        )

    def init_metricas_csv(self):
        header = [
            "ronda",
            "tiempo_total_ronda_seg",
            "tiempo_espera_clientes_seg",
            "tiempo_verif_clientes_seg",
            "tiempo_agregacion_fedavg_seg",
            "tiempo_subida_ipfs_seg",
            "tiempo_confirmacion_tx_seg",
            "gas_consumido",
            "clientes_validos",
            "clientes_descartados",
            "timestamp"
        ]
        for path in [self.archivo_csv_exp, self.archivo_csv_legacy]:
            if not path.exists():
                with open(path, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)

    def guardar_metricas(self, ronda, t_total, t_espera, t_verif, t_agg, t_ipfs, t_tx, gas, validos, descartados):
        fila = [
            ronda,
            t_total,
            t_espera,
            t_verif,
            t_agg,
            t_ipfs,
            t_tx,
            gas,
            validos,
            descartados,
            time.time()
        ]
        for path in [self.archivo_csv_exp, self.archivo_csv_legacy]:
            with open(path, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(fila)

    def upload_to_ipfs(self, data_bytes):
        try:
            files = {'file': data_bytes}
            response = requests.post(IPFS_API_URL, files=files, timeout=15)
            if response.status_code == 200:
                return response.json()['Hash']
            else:
                print(f"Error en IPFS: {response.text}")
                return None
        except Exception as e:
            print(f"Error de conexión con IPFS: {e}")
            return None

    def configure_fit(self, server_round: int, parameters: fl.common.Parameters, client_manager: fl.server.client_manager.ClientManager):
        # Marca de inicio exacto de la ronda federada en el servidor
        self.tiempo_inicio_ronda = time.time()
        client_instructions = super().configure_fit(server_round, parameters, client_manager)

        # Inyección de ataque simulado si procede
        if self.simulate_attack == "tampered_server" and server_round == self.attack_round:
            print(f"\n{'='*70}")
            print(f"[ATAQUE SIMULADO - SERVIDOR] Inyectando pesos adulterados en ronda {server_round}")
            print(f"Los clientes recibirán pesos manipulados que NO coincidirán con el CID de IPFS/Besu")
            print(f"{'='*70}\n")

            tampered_instructions = []
            for client_proxy, fit_ins in client_instructions:
                ndarrays = fl.common.parameters_to_ndarrays(fit_ins.parameters)
                tampered_ndarrays = [arr + 0.5 for arr in ndarrays]
                tampered_params = fl.common.ndarrays_to_parameters(tampered_ndarrays)
                tampered_instructions.append((client_proxy, fl.common.FitIns(tampered_params, fit_ins.config)))
            return tampered_instructions

        return client_instructions

    def aggregate_fit(self, server_round, results, failures):
        tiempo_recepcion_clientes = time.time()
        t_espera_clientes = tiempo_recepcion_clientes - self.tiempo_inicio_ronda

        if not results:
            print(f"Ronda {server_round}: Sin resultados de clientes")
            return None, {}

        # 1. Verificación ascendente de CIDs en Blockchain
        t_start_verif = time.time()
        valid_results = []
        descartados_count = 0

        for client_proxy, fit_res in results:
            client_cid = fit_res.metrics.get("cid")
            client_address = fit_res.metrics.get("address")

            if not client_cid or not client_address:
                print(f"Rechazando cliente {client_proxy.cid}: no reportó CID o dirección")
                descartados_count += 1
                continue

            try:
                # 1. Consultar Blockchain (Besu)
                blockchain_cid = self.contract.functions.getClientModel(
                    server_round,
                    Web3.to_checksum_address(client_address)
                ).call()

                # 2. Reconstruir el CID de los pesos recibidos vía Flower
                client_ndarrays = fl.common.parameters_to_ndarrays(fit_res.parameters)
                client_bytes = pickle.dumps(client_ndarrays)
                calculated_cid = self.upload_to_ipfs(client_bytes)

                # 3. Triple verificación (pesos == reportado == blockchain)
                if calculated_cid == client_cid == blockchain_cid:
                    print(f"Verificación exitosa para {client_address} (CID: {client_cid})")
                    valid_results.append((client_proxy, fit_res))
                else:
                    print(f"\n[ALERTA DE SEGURIDAD] Discrepancia tensorial o de registro en {client_address}.")
                    print(f"  -> Calculado: {calculated_cid} | Reportado: {client_cid} | Blockchain: {blockchain_cid}")
                    descartados_count += 1
            except Exception as e:
                print(f"Error validando cliente en blockchain/IPFS: {e}")
                descartados_count += 1

        t_verif_clientes = time.time() - t_start_verif

        # 2. Agregación FedAvg sobre clientes verificados
        t_start_agg = time.time()
        agg_params, agg_metrics = super().aggregate_fit(server_round, valid_results, failures)
        t_agg = time.time() - t_start_agg

        # 3. Subida a IPFS y confirmación en Blockchain
        gas_consumido = 0
        t_tx = 0.0
        t_ipfs = 0.0

        if agg_params is not None:
            t_start_ipfs = time.time()
            pesos = pickle.dumps(fl.common.parameters_to_ndarrays(agg_params))
            model_cid = self.upload_to_ipfs(pesos)
            t_ipfs = time.time() - t_start_ipfs

            if model_cid:
                print(f"Modelo global ronda {server_round} subido a IPFS: {model_cid}")
                gas_consumido, t_tx = self.send_transaction(server_round, model_cid)
            else:
                print(f"Error al subir modelo global de ronda {server_round} a IPFS")
        else:
            print(f"Ronda {server_round}: Agregación vacía (sin clientes válidos)")

        # 4. Medición total extremo a extremo
        t_total_ronda = time.time() - self.tiempo_inicio_ronda

        self.guardar_metricas(
            ronda=server_round,
            t_total=t_total_ronda,
            t_espera=t_espera_clientes,
            t_verif=t_verif_clientes,
            t_agg=t_agg,
            t_ipfs=t_ipfs,
            t_tx=t_tx,
            gas=gas_consumido,
            validos=len(valid_results),
            descartados=descartados_count
        )

        return agg_params, agg_metrics

    def send_transaction(self, round_id, model_cid):
        try:
            nonce = self.w3.eth.get_transaction_count(MEMBER1_ADDRESS, 'pending')
            tx = self.contract.functions.updateModel(round_id, model_cid).build_transaction({
                'from': MEMBER1_ADDRESS,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': self.w3.eth.chain_id
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=PRIV_KEY1)

            t_start_tx = time.time()
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"Transacción updateModel ronda {round_id} enviada: {tx_hash.hex()}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            t_tx = time.time() - t_start_tx
            gas_consumido = receipt.gasUsed

            print(f"Transacción confirmada en bloque {receipt.blockNumber} (Gas: {gas_consumido}, Tiempo: {t_tx:.3f}s)")
            return gas_consumido, t_tx

        except Exception as e:
            print(f"Error en transacción updateModel: {e}")
            return 0, 0.0


def fit_config(server_round: int):
    return {"server_round": server_round}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor Flower con Hyperledger Besu e IPFS")
    parser.add_argument("--exp", type=str, default="E1", help="ID del experimento (E1, E4, E5)")
    parser.add_argument("--run", type=int, default=1, help="Número de ejecución (1, 2, 3)")
    parser.add_argument("--rounds", type=int, default=30, help="Número de rondas federadas")
    parser.add_argument("--server-address", type=str, default="0.0.0.0:8081", help="Dirección gRPC de escucha")
    parser.add_argument("--min-clients", type=int, default=2, help="Mínimo de clientes para entrenar")
    parser.add_argument("--simulate-attack", type=str, choices=["none", "tampered_server"], default="none",
                        help="Simular servidor malicioso enviando pesos adulterados")
    parser.add_argument("--attack-round", type=int, default=2, help="Ronda en la que se inyecta el ataque")
    args = parser.parse_args()

    print(f"Iniciando Servidor FL con Besu - Exp: {args.exp}, Run: {args.run}, Rondas: {args.rounds}")
    if args.simulate_attack != "none":
        print(f"MODO DE ATAQUE ACTIVO: {args.simulate_attack} en ronda {args.attack_round}")

    server_strat = MiBesuServer(
        exp=args.exp,
        run=args.run,
        simulate_attack=args.simulate_attack,
        attack_round=args.attack_round,
        min_fit_clients=args.min_clients,
        min_available_clients=args.min_clients,
        on_fit_config_fn=fit_config,
    )

    fl.server.start_server(
        server_address=args.server_address,
        config=fl.server.ServerConfig(num_rounds=args.rounds),
        strategy=server_strat
    )