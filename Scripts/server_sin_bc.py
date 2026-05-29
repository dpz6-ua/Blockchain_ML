import time
import csv
import flwr as fl
import os
from model import NetCliente
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

class MiServerNormal(fl.server.strategy.FedAvg):
    def __init__(self, **kwargs):
        modelo_init = NetCliente()
        pesos_iniciales = [val.cpu().numpy() for _, val in modelo_init.state_dict().items()]
        
        self.path_metricas = Path("../Metricas/Server/")
        self.path_metricas.mkdir(parents=True, exist_ok=True)
        self.archivo_csv = self.path_metricas / "metricas_server_NO_bchain_2maquinas.csv"
        self.init_metricas_csv()
        
        super().__init__(
            initial_parameters=fl.common.ndarrays_to_parameters(pesos_iniciales), 
            **kwargs
        )        

    def init_metricas_csv(self):
        if not self.archivo_csv.exists():
            with open(self.archivo_csv, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["ronda", "tiempo_agregacion_seg", "timestamp"])

    def guardar_metricas(self, num_ronda, tiempo_ronda):
        with open(self.archivo_csv, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([num_ronda, tiempo_ronda, time.time()])

    def aggregate_fit(self, server_round, results, failures):
        if not results:
            return None, {}

        start_time = time.time()
        
        agg_params, agg_metrics = super().aggregate_fit(server_round, results, failures)
        
        tiempo_total = time.time() - start_time
        self.guardar_metricas(server_round, tiempo_total)
        
        print(f"Ronda {server_round} finalizada sin Blockchain")
        return agg_params, agg_metrics
       
def fit_config(server_round: int):
    return {"server_round": server_round}
       
if __name__ == "__main__":
    server_strat = MiServerNormal(
        min_fit_clients=2, 
        min_available_clients=2, 
        on_fit_config_fn=fit_config,
    )
    print("Servidor sin Blockchain iniciado")
    fl.server.start_server(
        server_address="0.0.0.0:8081",
        config=fl.server.ServerConfig(num_rounds=30),
        strategy=server_strat
    )