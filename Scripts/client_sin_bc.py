import json
import pickle
import flwr as fl
import os
import torch
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
METRICAS_DIR = PROJECT_DIR / "Metricas"
DATASET_PATH = PROJECT_DIR / "Dataset" / "traffic-images" / "dataset_etiquetado.csv"


class MiFlowerClient(fl.client.NumPyClient):
    def __init__(self, member_id, exp="E2", run=1, server_ip="127.0.0.1", train_data=None, test_data=None):
        self.member_id = member_id
        self.exp = exp
        self.run = run
        self.server_ip = server_ip

        self.model = NetCliente()
        self.train_data = train_data
        self.test_data = test_data

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

    def get_parameters(self, config):
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        start_fit = time.time()
        server_round = config.get("server_round", 1)

        if not isinstance(parameters, list):
            parameters = fl.common.parameters_to_ndarrays(parameters)

        print(f"[{self.member_id}] Iniciando entrenamiento local sin Blockchain (3 épocas)")

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
        t_total = time.time() - start_fit

        self.guardar_metricas(
            ronda=server_round,
            t_total=t_total,
            t_verif=0.0,
            t_train=t_train,
            t_ipfs=0.0,
            t_tx=0.0,
            gas=0,
            estado="EXITOSO"
        )

        num_ejemplos = len(self.train_data.dataset) if self.train_data else 1
        return new_params, num_ejemplos, {}

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
    parser = argparse.ArgumentParser(description="Cliente Flower Baseline SIN Blockchain")
    parser.add_argument("--member", type=int, choices=[2, 3], required=True, help="ID del miembro (2 o 3)")
    parser.add_argument("--exp", type=str, default="E2", help="ID del experimento (E2, E3)")
    parser.add_argument("--run", type=int, default=1, help="Número de ejecución (1, 2, 3)")
    parser.add_argument("--server-ip", type=str, default="127.0.0.1", help="IP del servidor Flower")
    parser.add_argument("--server-port", type=str, default="8081", help="Puerto gRPC de Flower")
    args = parser.parse_args()

    print(f"Iniciando Cliente {args.member} SIN Blockchain - Exp: {args.exp}, Run: {args.run}, Servidor: {args.server_ip}:{args.server_port}")

    train_data, test_data = load_data(str(DATASET_PATH))

    client = MiFlowerClient(
        member_id=args.member,
        exp=args.exp,
        run=args.run,
        server_ip=args.server_ip,
        train_data=train_data,
        test_data=test_data
    )

    fl.client.start_client(
        server_address=f"{args.server_ip}:{args.server_port}",
        client=client.to_client()
    )