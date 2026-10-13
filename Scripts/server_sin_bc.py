import time
import csv
import flwr as fl
import os
import argparse
from model import NetCliente
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
METRICAS_DIR = PROJECT_DIR / "Metricas"


class MiServerNormal(fl.server.strategy.FedAvg):
    def __init__(self, exp="E2", run=1, **kwargs):
        self.exp = exp
        self.run = run
        self.tiempo_inicio_ronda = 0.0

        modelo_init = NetCliente()
        pesos_iniciales = [val.cpu().numpy() for _, val in modelo_init.state_dict().items()]

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

    def configure_fit(self, server_round: int, parameters: fl.common.Parameters, client_manager: fl.server.client_manager.ClientManager):
        # Marca de inicio exacto de la ronda federada en el servidor
        self.tiempo_inicio_ronda = time.time()
        return super().configure_fit(server_round, parameters, client_manager)

    def aggregate_fit(self, server_round, results, failures):
        tiempo_recepcion_clientes = time.time()
        t_espera_clientes = tiempo_recepcion_clientes - self.tiempo_inicio_ronda

        if not results:
            return None, {}

        t_start_agg = time.time()
        agg_params, agg_metrics = super().aggregate_fit(server_round, results, failures)
        t_agg = time.time() - t_start_agg

        # Medición total extremo a extremo
        t_total_ronda = time.time() - self.tiempo_inicio_ronda

        self.guardar_metricas(
            ronda=server_round,
            t_total=t_total_ronda,
            t_espera=t_espera_clientes,
            t_verif=0.0,
            t_agg=t_agg,
            t_ipfs=0.0,
            t_tx=0.0,
            gas=0,
            validos=len(results),
            descartados=0
        )

        print(f"Ronda {server_round} finalizada sin Blockchain (Tiempo total: {t_total_ronda:.3f}s)")
        return agg_params, agg_metrics


def fit_config(server_round: int):
    return {"server_round": server_round}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor Flower Baseline SIN Blockchain")
    parser.add_argument("--exp", type=str, default="E2", help="ID del experimento (E2, E3)")
    parser.add_argument("--run", type=int, default=1, help="Número de ejecución (1, 2, 3)")
    parser.add_argument("--rounds", type=int, default=30, help="Número de rondas federadas")
    parser.add_argument("--server-address", type=str, default="0.0.0.0:8081", help="Dirección gRPC de escucha")
    parser.add_argument("--min-clients", type=int, default=2, help="Mínimo de clientes para entrenar")
    args = parser.parse_args()

    print(f"Iniciando Servidor FL SIN Blockchain - Exp: {args.exp}, Run: {args.run}, Rondas: {args.rounds}")

    server_strat = MiServerNormal(
        exp=args.exp,
        run=args.run,
        min_fit_clients=args.min_clients,
        min_available_clients=args.min_clients,
        on_fit_config_fn=fit_config,
    )

    fl.server.start_server(
        server_address=args.server_address,
        config=fl.server.ServerConfig(num_rounds=args.rounds),
        strategy=server_strat
    )