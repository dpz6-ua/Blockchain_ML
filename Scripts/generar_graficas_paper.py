#!/usr/bin/env python3
# ==============================================================================
# Script para generar las gráficas del artículo con las métricas consolidadas
# Compatible con inglés ('en') y español ('es')
# ==============================================================================

import os
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib_paper'

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
METRICAS_DIR = PROJECT_DIR / "Metricas"

# Directorios de destino para las figuras
DEST_DIRS = [
    PROJECT_DIR / "Articulo_Springer" / "figures",
    PROJECT_DIR / "Articulo" / "figuras",
    PROJECT_DIR.parent / "TFG_Articulo" / "figuras"
]

# Configuración de estilo IEEE / Paper científico
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'Helvetica'],
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.titlesize': 14,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight'
})

COLORS = {
    'E1': '#D9534F',  # Soft Red
    'E2': '#6C757D',  # Neutral Gray
    'E3': '#0275D8',  # Institutional Blue
    'E4': '#5CB85C',  # Muted Green
    'E5': '#6F42C1',  # Purple
}

def guardar_figura(fig, nombre_archivo):
    for d in DEST_DIRS:
        if d.exists():
            ruta = d / nombre_archivo
            fig.savefig(ruta)
            print(f"Guardado: {ruta}")


def cargar_datos_rondas():
    datos = {}
    for exp in ['E1', 'E2', 'E3', 'E4', 'E5']:
        series_runs = []
        for r in range(1, 4):
            c2_p = METRICAS_DIR / exp / f"run_{r}" / "client_2.csv"
            c3_p = METRICAS_DIR / exp / f"run_{r}" / "client_3.csv"
            if c2_p.exists() and c3_p.exists():
                df2 = pd.read_csv(c2_p)
                df3 = pd.read_csv(c3_p)
                t2 = df2['tiempo_total_cliente_seg'].values[:30]
                t3 = df3['tiempo_total_cliente_seg'].values[:30]
                t_prom = (t2 + t3) / 2.0
                series_runs.append(t_prom)
        if series_runs:
            mat = np.array(series_runs)  # shape: (runs, 30)
            datos[exp] = {
                'media_ronda': np.mean(mat, axis=0),
                'desv_ronda': np.std(mat, axis=0),
                'matriz': mat
            }
    return datos


def generar_figura_tiempo_ronda(datos, lang='en'):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    rondas = np.arange(1, 31)

    if lang == 'en':
        labels = {
            'E1': 'E1: 4 val · with BC (1 Workstation)',
            'E2': 'E2: Baseline without BC (1 Workstation)',
            'E3': 'E3: Baseline without BC (2 Workstations)',
            'E4': 'E4: 4 val · with BC (2 Workstations)',
            'E5': 'E5: 7 val · with BC (2 Workstations)',
        }
        xlabel = 'Federated Round'
        ylabel = 'Total Cycle Time per Round (s)'
        title = 'Federated Round Cycle Time (Consolidated Mean of 3 Runs)'
    else:
        labels = {
            'E1': 'E1: 4 val · con BC (1 PC)',
            'E2': 'E2: Baseline sin BC (1 PC)',
            'E3': 'E3: Baseline sin BC (2 PCs)',
            'E4': 'E4: 4 val · con BC (2 PCs)',
            'E5': 'E5: 7 val · con BC (2 PCs)',
        }
        xlabel = 'Ronda Federada'
        ylabel = 'Tiempo total por ronda (s)'
        title = 'Tiempo de Ronda Federada (Media consolidada de 3 ejecuciones)'

    markers = {'E1': 'o', 'E2': 's', 'E3': '^', 'E4': 'D', 'E5': 'v'}

    for exp in ['E1', 'E2', 'E4', 'E5', 'E3']:
        if exp in datos:
            mu = datos[exp]['media_ronda']
            std = datos[exp]['desv_ronda']
            ax.plot(rondas, mu, label=labels[exp], color=COLORS[exp], marker=markers[exp], markersize=4, linewidth=1.5, alpha=0.9)
            ax.fill_between(rondas, mu - std, mu + std, color=COLORS[exp], alpha=0.12)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(range(1, 31, 2))
    ax.set_xlim(0.5, 30.5)
    ax.set_ylim(60, 160)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', framealpha=0.95)

    guardar_figura(fig, 'tiempo_ronda_todas.png')
    plt.close(fig)


def generar_figura_coste_blockchain(lang='en'):
    fig, ax = plt.subplots(figsize=(7, 4.5))

    sin_bc = [75.70, 66.62]
    con_bc = [85.42, 72.96]

    if lang == 'en':
        grupos = ['Single-Workstation Setup\n(1 Workstation)', 'Distributed Setup\n(2 Workstations)']
        label_sin = 'Baseline (Without Blockchain)'
        label_con = 'With Blockchain / IPFS'
        ylabel = 'Median Cycle Time per Round (s)'
        title = 'Temporal Overhead of the Blockchain Layer'
    else:
        grupos = ['Escenario Monomáquina\n(1 Estación)', 'Escenario Distribuido\n(2 Estaciones)']
        label_sin = 'Baseline (Sin Blockchain)'
        label_con = 'Con Blockchain / IPFS'
        ylabel = 'Tiempo mediano por ronda (s)'
        title = 'Sobrecoste Temporal de la Capa Blockchain'

    x = np.arange(len(grupos))
    width = 0.32

    ax.bar(x - width/2, sin_bc, width, label=label_sin, color='#6C757D', edgecolor='black', linewidth=0.8)
    ax.bar(x + width/2, con_bc, width, label=label_con, color='#0275D8', edgecolor='black', linewidth=0.8)

    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(grupos)
    ax.set_ylim(0, 105)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', framealpha=0.95)

    for i in range(len(grupos)):
        delta = con_bc[i] - sin_bc[i]
        pct = (delta / sin_bc[i]) * 100
        ax.annotate(f"+{delta:.2f} s\n(+{pct:.1f}%)",
                    xy=(x[i] + width/2, con_bc[i]), xytext=(0, 6),
                    textcoords="offset points", ha='center', va='bottom',
                    fontweight='bold', color='#D9534F', fontsize=10)

        ax.text(x[i] - width/2, sin_bc[i] / 2, f"{sin_bc[i]:.2f}s", ha='center', va='center', color='white', fontweight='bold', fontsize=10)
        ax.text(x[i] + width/2, con_bc[i] / 2, f"{con_bc[i]:.2f}s", ha='center', va='center', color='white', fontweight='bold', fontsize=10)

    guardar_figura(fig, 'coste_blockchain.png')
    plt.close(fig)


def generar_figura_coste_distribucion(lang='en'):
    fig, ax = plt.subplots(figsize=(7, 4.5))

    est1 = [75.70, 85.42]
    est2 = [66.62, 72.96]

    if lang == 'en':
        grupos = ['Without Blockchain\n(E2 vs. E3)', 'With Blockchain\n(E1 vs. E4)']
        label_est1 = '1 Workstation (Single-Machine)'
        label_est2 = '2 Workstations (Distributed)'
        ylabel = 'Median Cycle Time per Round (s)'
        title = 'Effect of Physical Distribution (Contention Mitigation)'
    else:
        grupos = ['Sin Blockchain\n(E2 vs E3)', 'Con Blockchain\n(E1 vs E4)']
        label_est1 = '1 Estación (Monomáquina)'
        label_est2 = '2 Estaciones (Distribuido)'
        ylabel = 'Tiempo mediano por ronda (s)'
        title = 'Efecto de la Distribución Física (Mitigación de Contención)'

    x = np.arange(len(grupos))
    width = 0.32

    ax.bar(x - width/2, est1, width, label=label_est1, color='#F0AD4E', edgecolor='black', linewidth=0.8)
    ax.bar(x + width/2, est2, width, label=label_est2, color='#5CB85C', edgecolor='black', linewidth=0.8)

    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(grupos)
    ax.set_ylim(0, 105)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', framealpha=0.95)

    for i in range(len(grupos)):
        delta = est2[i] - est1[i]
        pct = (delta / est1[i]) * 100
        ax.annotate(f"{delta:.2f} s\n({pct:.1f}%)",
                    xy=(x[i] + width/2, est2[i]), xytext=(0, 6),
                    textcoords="offset points", ha='center', va='bottom',
                    fontweight='bold', color='#28A745', fontsize=10)

        ax.text(x[i] - width/2, est1[i] / 2, f"{est1[i]:.2f}s", ha='center', va='center', color='black', fontweight='bold', fontsize=10)
        ax.text(x[i] + width/2, est2[i] / 2, f"{est2[i]:.2f}s", ha='center', va='center', color='white', fontweight='bold', fontsize=10)

    guardar_figura(fig, 'coste_distribucion.png')
    plt.close(fig)


def generar_figura_tiempo_confirmacion(lang='en'):
    fig, ax = plt.subplots(figsize=(7.5, 4.5))

    t_cliente = [2.85, 2.84, 2.94]
    t_servidor = [5.14, 2.89, 2.99]

    if lang == 'en':
        configuraciones = ['E1 (Local, 4 vals)', 'E4 (Distributed, 4 vals)', 'E5 (Distributed, 7 vals)']
        label_cli = 'Client (registerClientModel)'
        label_srv = 'Coordinator (updateModel)'
        ylabel = 'Average Confirmation Latency (s)'
        title = 'On-Chain Confirmation Latency by Topology and Validators'
        annotation_delta = r"$\Delta = +0.10$ s" + "\n(7-val consensus)"
    else:
        configuraciones = ['E1 (Local, 4 vals)', 'E4 (Distribuido, 4 vals)', 'E5 (Distribuido, 7 vals)']
        label_cli = 'Cliente (registerClientModel)'
        label_srv = 'Servidor (updateModel)'
        ylabel = 'Latencia media de confirmación (s)'
        title = 'Latencia de Confirmación On-Chain según Topología y Validadores'
        annotation_delta = "Δ = +0.10 s\n(Consenso 7 vals)"

    x = np.arange(len(configuraciones))
    width = 0.32

    ax.bar(x - width/2, t_cliente, width, label=label_cli, color='#0275D8', edgecolor='black', linewidth=0.8)
    ax.bar(x + width/2, t_servidor, width, label=label_srv, color='#6F42C1', edgecolor='black', linewidth=0.8)

    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(configuraciones)
    ax.set_ylim(0, 6.5)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', framealpha=0.95)

    for i in range(len(configuraciones)):
        ax.text(x[i] - width/2, t_cliente[i] + 0.12, f"{t_cliente[i]:.2f}s", ha='center', va='bottom', fontsize=9.5, fontweight='bold')
        ax.text(x[i] + width/2, t_servidor[i] + 0.12, f"{t_servidor[i]:.2f}s", ha='center', va='bottom', fontsize=9.5, fontweight='bold')

    ax.annotate(annotation_delta, xy=(x[2] - width/2, t_cliente[2]), xytext=(0, 25),
                textcoords="offset points", ha='center', va='bottom',
                arrowprops=dict(arrowstyle="->", color='#333333', lw=1.0),
                fontsize=8.5, color='#333333', fontweight='bold')

    guardar_figura(fig, 'tiempo_confirmacion.png')
    plt.close(fig)


def generar_figura_consumo_gas(lang='en'):
    fig, ax = plt.subplots(figsize=(8, 4.5))

    rondas = np.arange(0, 31)
    gas_servidor = [186749] + [169649] * 30
    gas_cliente = [np.nan] + [160200] * 30

    if lang == 'en':
        label_srv = 'Coordinator (updateModel)'
        label_cli = 'Client (registerClientModel)'
        xlabel = 'Federated Round'
        ylabel = 'Gas Consumption (units)'
        title = 'Ethereum Virtual Machine (EVM) Gas Consumption'
        annotation_cold = "Initial cold write (SSTORE):\n186,749 gas (+17,100)"
        annotation_srv_inv = "Invariant O(1): 169,649 gas"
        annotation_cli_inv = "Invariant O(1): 160,200 gas"
    else:
        label_srv = 'Servidor (updateModel)'
        label_cli = 'Cliente (registerClientModel)'
        xlabel = 'Ronda Federada'
        ylabel = 'Consumo de Gas (unidades)'
        title = 'Consumo de Gas en la Máquina Virtual de Ethereum (EVM)'
        annotation_cold = "Cold write inicial (SSTORE):\n186.749 gas (+17.100)"
        annotation_srv_inv = "Invariable O(1): 169.649 gas"
        annotation_cli_inv = "Invariable O(1): 160.200 gas"

    ax.plot(rondas, gas_servidor, label=label_srv, color='#6F42C1', marker='o', linewidth=1.8, markersize=4)
    ax.plot(rondas[1:], gas_cliente[1:], label=label_cli, color='#0275D8', marker='s', linewidth=1.8, markersize=4)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(range(0, 31, 2))
    ax.set_xlim(-0.5, 30.5)
    ax.set_ylim(145000, 208000)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', framealpha=0.95)

    ax.annotate(annotation_cold, xy=(0, 186749), xytext=(2.0, 197000),
                arrowprops=dict(facecolor='#333333', shrink=0.08, width=1, headwidth=6),
                fontsize=9, fontweight='bold', color='#333333')

    ax.text(10, 173500, annotation_srv_inv, color='#6F42C1', fontweight='bold', fontsize=9.5)
    ax.text(10, 154500, annotation_cli_inv, color='#0275D8', fontweight='bold', fontsize=9.5)

    guardar_figura(fig, 'consumo_gas.png')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generar gráficas científicas consolidadas del paper.")
    parser.add_argument('--lang', choices=['en', 'es'], default='en', help="Idioma de las figuras ('en' por defecto, 'es' para español)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"GENERADOR DE GRÁFICAS CIENTÍFICAS CON DATOS CONSOLIDADOS (Idioma: {args.lang.upper()})")
    print("=" * 70)

    datos = cargar_datos_rondas()
    print(f"Datos cargados para: {list(datos.keys())}")

    generar_figura_tiempo_ronda(datos, lang=args.lang)
    generar_figura_coste_blockchain(lang=args.lang)
    generar_figura_coste_distribucion(lang=args.lang)
    generar_figura_tiempo_confirmacion(lang=args.lang)
    generar_figura_consumo_gas(lang=args.lang)

    print(f"\n¡Todas las gráficas en {args.lang.upper()} se han generado y actualizado con éxito a 300 DPI!")


if __name__ == "__main__":
    main()
