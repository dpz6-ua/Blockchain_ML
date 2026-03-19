import json
import pickle
import flwr as fl
import os
import requests
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

parser = argparse.ArgumentParser()
parser.add_argument("--member", type=int, choices=[2, 3], required=True, help="ID del miembro")
args = parser.parse_args()

class MiFlowerClient(fl.client.NumPyClient):
    def __init__(self, train_data, test_data):
        self.model = NetCliente()
        self.train_data = train_data
        self.test_data = test_data
        
        self.metricas_path = Path("../Metricas/Client/")
        self.metricas_path.mkdir(parents=True, exist_ok=True)
        # Cambiamos el nombre del CSV para diferenciar la comparativa
        self.csv_file = self.metricas_path / f"metricas_client_{args.member}_NO_bchain.csv"
        self.init_metricas_csv()
      
    def init_metricas_csv(self):
        if not self.csv_file.exists():
            with open(self.csv_file, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["ronda", "tiempo_total_local", "timestamp"])

    def guardar_metricas(self, num_ronda, tiempo_total):
        with open(self.csv_file, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([num_ronda, tiempo_total, time.time()])         
         
    def get_parameters(self, config):
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        start_fit = time.time()
        
        if not isinstance(parameters, list):
            parameters = fl.common.parameters_to_ndarrays(parameters)
            
        print(f"[{args.member}] Iniciando entrenamiento local sin Blockchain")
        
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
        
        new_params = self.get_parameters(config={})
        server_round = config.get("server_round", 1)
        
        total_time = time.time() - start_fit
        self.guardar_metricas(server_round, total_time)
            
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
    train_data, test_data = load_data("../Dataset/traffic-images/dataset_etiquetado.csv")
    fl.client.start_client(
        server_address="127.0.0.1:8081", 
        client=MiFlowerClient(train_data, test_data).to_client()
    )