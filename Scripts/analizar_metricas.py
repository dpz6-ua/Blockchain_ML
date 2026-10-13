import os
import glob
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
METRICAS_DIR = PROJECT_DIR / "Metricas"

EXP_METADATA = {
    "E1": {"maquinas": 1, "bc": "Sí", "validadores": 4, "desc": "Sobrecarga BC local", "baseline": "E2"},
    "E2": {"maquinas": 1, "bc": "No", "validadores": "-", "desc": "Baseline local", "baseline": None},
    "E3": {"maquinas": 2, "bc": "No", "validadores": "-", "desc": "Baseline distribuido", "baseline": None},
    "E4": {"maquinas": 2, "bc": "Sí", "validadores": 4, "desc": "Sobrecarga BC distribuida", "baseline": "E3"},
    "E5": {"maquinas": 2, "bc": "Sí", "validadores": 7, "desc": "Escalabilidad IBFT 2.0", "baseline": "E3"},
}

LEGACY_MAP = {
    "E1": {"server": "metricas_server_bchain_4vals.csv", "c2": "metricas_client_2_bchain_4vals.csv", "c3": "metricas_client_3_bchain_4vals.csv"},
    "E2": {"server": "metricas_server_NO_bchain.csv", "c2": "metricas_client_2_NO_bchain.csv", "c3": "metricas_client_3_NO_bchain.csv"},
    "E3": {"server": "metricas_server_NO_bchain_2maquinas.csv", "c2": "metricas_client_2_NO_bchain_2maquinas.csv", "c3": "metricas_client_3_NO_bchain_2maquinas.csv"},
    "E4": {"server": "metricas_server_bchain_4vals_2maquinas.csv", "c2": "metricas_client_2_bchain_4vals_2maquinas.csv", "c3": "metricas_client_3_bchain_4vals_2maquinas.csv"},
    "E5": {"server": "metricas_server_bchain_7vals_2maquinas.csv", "c2": "metricas_client_2_bchain_7vals_2maquinas.csv", "c3": "metricas_client_3_bchain_7vals_2maquinas.csv"},
}


def cargar_datos_experimento(exp_id):
    """
    Busca todas las ejecuciones (runs) disponibles para un experimento dado.
    Soporta la nueva estructura jerárquica Metricas/{exp}/run_{run}/
    y la estructura legacy de Metricas/Client/ y Metricas/Server/.
    """
    runs = {}

    # 1. Buscar en estructura nueva: Metricas/{exp_id}/run_*/
    exp_dir = METRICAS_DIR / exp_id
    if exp_dir.exists():
        run_dirs = sorted(exp_dir.glob("run_*"))
        for r_dir in run_dirs:
            try:
                run_num = int(r_dir.name.replace("run_", ""))
            except ValueError:
                run_num = r_dir.name

            server_f = r_dir / "server.csv"
            c2_f = r_dir / "client_2.csv"
            c3_f = r_dir / "client_3.csv"

            if c2_f.exists() and c3_f.exists():
                runs[run_num] = {
                    "server": pd.read_csv(server_f) if server_f.exists() else None,
                    "client_2": pd.read_csv(c2_f),
                    "client_3": pd.read_csv(c3_f),
                }

    # 2. Si no hay runs en la nueva estructura, buscar archivos legacy (Run 1 histórico)
    if not runs and exp_id in LEGACY_MAP:
        cfg = LEGACY_MAP[exp_id]
        s_path = METRICAS_DIR / "Server" / cfg["server"]
        c2_path = METRICAS_DIR / "Client" / cfg["c2"]
        c3_path = METRICAS_DIR / "Client" / cfg["c3"]

        if c2_path.exists() and c3_path.exists():
            runs[1] = {
                "server": pd.read_csv(s_path) if s_path.exists() else None,
                "client_2": pd.read_csv(c2_path),
                "client_3": pd.read_csv(c3_path),
            }

    # 3. Buscar archivos con patrón _runN en legacy
    run_pattern_c2 = sorted(METRICAS_DIR.glob(f"Client/metricas_client_2_{exp_id}_run*.csv"))
    for f2 in run_pattern_c2:
        try:
            r_num = int(f2.stem.split("run")[-1])
        except Exception:
            continue
        f3 = METRICAS_DIR / "Client" / f"metricas_client_3_{exp_id}_run{r_num}.csv"
        fs = METRICAS_DIR / "Server" / f"metricas_server_{exp_id}_run{r_num}.csv"
        if f3.exists():
            runs[r_num] = {
                "server": pd.read_csv(fs) if fs.exists() else None,
                "client_2": pd.read_csv(f2),
                "client_3": pd.read_csv(f3),
            }

    return runs


def extraer_columna_tiempo_cliente(df):
    for col in ["tiempo_total_cliente_seg", "tiempo_total_con_commit", "tiempo_total_local"]:
        if col in df.columns:
            return df[col]
    # Si no, buscar la primera columna que contenga 'tiempo' y no 'confirmacion'
    cols = [c for c in df.columns if "tiempo" in c and "confirmacion" not in c and "verif" not in c and "entrenamiento" not in c and "subida" not in c]
    if cols:
        return df[cols[0]]
    raise KeyError("No se encontró columna de tiempo total en el DataFrame del cliente")


def analizar():
    print("\n" + "=" * 90)
    print("ANÁLISIS ESTADÍSTICO DE EXPERIMENTOS DE FEDERATED LEARNING + BLOCKCHAIN")
    print("=" * 90)

    resumen_filas = []
    detalle_por_run = []

    for exp_id, meta in EXP_METADATA.items():
        runs = cargar_datos_experimento(exp_id)
        if not runs:
            print(f"[{exp_id}] Sin datos registrados en Metricas/")
            continue

        print(f"\nProcesando {exp_id} ({meta['desc']}) - {len(runs)} ejecuciones encontradas...")

        todos_los_tiempos_promedio_por_ronda = []
        medians_runs = []
        means_runs = []
        stds_runs = []

        for r_num, data in sorted(runs.items(), key=lambda x: str(x[0])):
            df2 = data["client_2"]
            df3 = data["client_3"]

            t2 = extraer_columna_tiempo_cliente(df2)
            t3 = extraer_columna_tiempo_cliente(df3)

            # Promedio por ronda entre los 2 clientes (definición idéntica a la del paper)
            min_len = min(len(t2), len(t3))
            t_ronda_run = (t2.iloc[:min_len].values + t3.iloc[:min_len].values) / 2.0

            todos_los_tiempos_promedio_por_ronda.extend(t_ronda_run)

            r_med = float(np.median(t_ronda_run))
            r_mean = float(np.mean(t_ronda_run))
            r_std = float(np.std(t_ronda_run, ddof=1)) if len(t_ronda_run) > 1 else 0.0

            medians_runs.append(r_med)
            means_runs.append(r_mean)
            stds_runs.append(r_std)

            detalle_por_run.append({
                "Exp": exp_id,
                "Run": r_num,
                "Rondas": min_len,
                "Mediana_s": round(r_med, 2),
                "Media_s": round(r_mean, 2),
                "Desv_s": round(r_std, 2)
            })

            print(f"   -> Run {r_num} ({min_len} rondas): Mediana={r_med:.2f} s | Media={r_mean:.2f} s | Desv={r_std:.2f} s")

        # Métricas globales agregadas entre todas las ejecuciones
        global_arr = np.array(todos_los_tiempos_promedio_por_ronda)
        global_med = float(np.median(global_arr))
        global_mean = float(np.mean(global_arr))
        global_std = float(np.std(global_arr, ddof=1)) if len(global_arr) > 1 else 0.0

        # Error estándar de la media
        se = global_std / np.sqrt(len(global_arr)) if len(global_arr) > 1 else 0.0

        resumen_filas.append({
            "Exp": exp_id,
            "Maq": meta["maquinas"],
            "Config": f"{meta['validadores']} val · con BC" if meta['bc'] == "Sí" else "Baseline sin BC",
            "Runs": len(runs),
            "Rondas_Total": len(global_arr),
            "Mediana_s": round(global_med, 2),
            "Media_s": round(global_mean, 2),
            "Desv_s": round(global_std, 2),
            "SE_s": round(se, 2),
        })

    # DataFrames finales
    df_resumen = pd.DataFrame(resumen_filas)
    df_detalle = pd.DataFrame(detalle_por_run)

    # Guardar en Metricas/
    out_dir = METRICAS_DIR / "consolidado"
    out_dir.mkdir(parents=True, exist_ok=True)

    df_resumen.to_csv(out_dir / "tabla_III_consolidada.csv", index=False)
    df_detalle.to_csv(out_dir / "detalle_por_ejecucion.csv", index=False)

    print("\n" + "=" * 90)
    print("CUADRO III ACTUALIZADO: TIEMPO TOTAL POR RONDA (Consolidado entre ejecuciones)")
    print("=" * 90)
    print(df_resumen.to_string(index=False))

    # Análisis de sobrecoste
    print("\n" + "=" * 90)
    print("SOBRECOSTE TEMPORAL AISLADO DE LA CAPA BLOCKCHAIN:")
    print("=" * 90)
    try:
        e1_med = df_resumen.loc[df_resumen["Exp"] == "E1", "Mediana_s"].values[0]
        e2_med = df_resumen.loc[df_resumen["Exp"] == "E2", "Mediana_s"].values[0]
        diff_local = e1_med - e2_med
        pct_local = (diff_local / e2_med) * 100
        print(f"• Escenario Monomáquina (E1 vs E2):")
        print(f"  De {e2_med:.2f} s a {e1_med:.2f} s -> Sobrecoste: +{diff_local:.2f} s (+{pct_local:.1f} %)")

        e4_med = df_resumen.loc[df_resumen["Exp"] == "E4", "Mediana_s"].values[0]
        e3_med = df_resumen.loc[df_resumen["Exp"] == "E3", "Mediana_s"].values[0]
        diff_dist = e4_med - e3_med
        pct_dist = (diff_dist / e3_med) * 100
        print(f"• Escenario Distribuido (E4 vs E3):")
        print(f"  De {e3_med:.2f} s a {e4_med:.2f} s -> Sobrecoste: +{diff_dist:.2f} s (+{pct_dist:.1f} %)")

        e5_med = df_resumen.loc[df_resumen["Exp"] == "E5", "Mediana_s"].values[0]
        diff_ibft = e5_med - e4_med
        print(f"• Escalado IBFT 2.0 (4 vs 7 validadores: E4 vs E5):")
        print(f"  De {e4_med:.2f} s a {e5_med:.2f} s -> Variación: {diff_ibft:+.2f} s")
    except Exception as e:
        print(f"No se pudieron calcular todos los sobrecostes: {e}")

    print("\nArchivos exportados en:")
    print(f" - {out_dir / 'tabla_III_consolidada.csv'}")
    print(f" - {out_dir / 'detalle_por_ejecucion.csv'}")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    analizar()
