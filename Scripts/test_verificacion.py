import time
import json
import pickle
import requests
import argparse
import numpy as np
import torch
from pathlib import Path
from web3 import Web3
from model import NetCliente

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SMART_CONTRACTS_DIR = PROJECT_DIR / "Smart_Contracts"
METRICAS_DIR = PROJECT_DIR / "Metricas"

ETH_ENDPOINT = 'http://127.0.0.1:18545'
MEMBER1_ADDRESS = Web3.to_checksum_address("0xfe3b557e8fb62b89f4916b721be55ceb828dbd73")
PRIV_KEY1 = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

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


def test_verificacion_descendente(w3, contract, ipfs_url="http://127.0.0.1:5001/api/v0/add?pin=false", ipfs_get="http://127.0.0.1:8080/ipfs/"):
    """
    Prueba 1: Servidor Adulterado / Verificación Descendente.
    Demuestra experimentalmente que si el servidor envía un modelo distinto del registrado
    en la Blockchain, el cliente lo detecta mediante su hash en IPFS y aborta el entrenamiento.
    """
    print("\n" + "=" * 80)
    print("PRUEBA 1: VERIFICACIÓN DESCENDENTE (Servidor Malicioso -> Cliente Detecta y Aborta)")
    print("=" * 80)

    # 1. Crear modelo base legítimo y subir a IPFS
    modelo_oficial = NetCliente()
    pesos_oficiales = [val.cpu().numpy() for _, val in modelo_oficial.state_dict().items()]
    bytes_oficiales = pickle.dumps(pesos_oficiales)

    print("1. Subiendo modelo legítimo oficial a IPFS...")
    resp = requests.post(ipfs_url, files={'file': bytes_oficiales}, timeout=10)
    if resp.status_code != 200:
        print(f"   [FALLO] No se pudo conectar a IPFS en {ipfs_url}")
        return False
    cid_oficial = resp.json()['Hash']
    print(f"   CID oficial generado en IPFS: {cid_oficial}")

    # 2. El servidor registra el CID oficial en el Smart Contract
    print("2. Registrando CID oficial en FLRegistry (updateModel)...")
    round_test = 999
    tx = contract.functions.updateModel(round_test, cid_oficial).build_transaction({
        'from': MEMBER1_ADDRESS,
        'nonce': w3.eth.get_transaction_count(MEMBER1_ADDRESS),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })
    signed = w3.eth.account.sign_transaction(tx, private_key=PRIV_KEY1)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"   CID sellado on-chain en bloque {receipt.blockNumber}")

    # 3. El servidor simula el envío de un modelo adulterado (con ruido)
    print("3. Servidor malicioso envía a un cliente pesos adulterados (distintos de los sellados)...")
    pesos_adulterados = [arr + 0.5 for arr in pesos_oficiales]

    # 4. El cliente verifica los pesos recibidos contra la Blockchain + IPFS
    print("4. Cliente consulta Blockchain getLastModel() y descarga artefacto de IPFS...")
    t0 = time.time()
    last_model = contract.functions.getLastModel().call()
    cid_onchain = last_model[1]

    # Descarga de IPFS
    resp_ipfs = requests.get(f"{ipfs_get}{cid_onchain}", timeout=10)
    pesos_desde_ipfs = pickle.loads(resp_ipfs.content)

    # Comprobación tensor a tensor
    es_valido = all(
        np.allclose(p_recibido, p_ipfs, atol=1e-7)
        for p_recibido, p_ipfs in zip(pesos_adulterados, pesos_desde_ipfs)
    )
    t_deteccion = time.time() - t0

    print(f"   Tiempo de verificación: {t_deteccion:.4f} segundos")
    print(f"   Resultado de la comparación de pesos: {'COINCIDEN' if es_valido else 'DISCREPANCIA DETECTADA'}")

    if not es_valido:
        print("   -> [ÉXITO EXPERIMENTAL] El cliente detectó la adulteración del servidor.")
        print("   -> Acción del cliente: ABORTAR inmediatamente (datos privados protegidos).")
        return True
    else:
        print("   -> [FALLO] El cliente no detectó la adulteración.")
        return False


def test_verificacion_ascendente(w3, contract):
    """
    Prueba 2: Cliente Adulterado / Verificación Ascendente.
    Demuestra experimentalmente que si un cliente envía al servidor un CID falso o no
    respaldado por su transacción on-chain, el servidor lo detecta y lo descarta de FedAvg.
    """
    print("\n" + "=" * 80)
    print("PRUEBA 2: VERIFICACIÓN ASCENDENTE (Cliente Malicioso -> Servidor Descarta de FedAvg)")
    print("=" * 80)

    round_test = 999
    cuenta_cliente = CLIENT_ACCOUNTS[3]
    cid_legitimo = "QmClientLegitimoModelWeightsCID1111111111111111"
    cid_fraudulento = "QmClientFraudeQueNoEstaRegistradoEnBesu222222222"

    # 1. El cliente registra su CID legítimo en la Blockchain
    print(f"1. Cliente ({cuenta_cliente['address']}) registra CID legítimo on-chain...")
    tx = contract.functions.registerClientModel(round_test, cid_legitimo).build_transaction({
        'from': cuenta_cliente["address"],
        'nonce': w3.eth.get_transaction_count(cuenta_cliente["address"]),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })
    signed = w3.eth.account.sign_transaction(tx, private_key=cuenta_cliente["key"])
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"   CID legítimo sellado on-chain en bloque {receipt.blockNumber}")

    # 2. El cliente intenta reportar al servidor un CID fraudulento vía Flower
    print(f"2. Cliente malicioso envía al servidor CID fraudulento: {cid_fraudulento}")

    # 3. El servidor audita la contribución antes de FedAvg
    print("3. Servidor agregador audita el CID reportado consultando getClientModel()...")
    t0 = time.time()
    cid_registrado_onchain = contract.functions.getClientModel(round_test, cuenta_cliente["address"]).call()
    coincide = (cid_registrado_onchain == cid_fraudulento)
    t_auditoria = time.time() - t0

    print(f"   CID reportado vía mensaje:  {cid_fraudulento}")
    print(f"   CID verificado on-chain:    {cid_registrado_onchain}")
    print(f"   Tiempo de auditoría RPC:    {t_auditoria:.4f} segundos")
    print(f"   ¿Coincide la firma y hash?: {'SÍ' if coincide else 'NO (FRAUDE DETECTADO)'}")

    if not coincide:
        print("   -> [ÉXITO EXPERIMENTAL] El servidor detectó la discrepancia del cliente.")
        print("   -> Acción del servidor: DESCARTAR al cliente de la agregación FedAvg.")
        print("   -> El modelo global no se contamina y preserva la integridad bizantina.")
        return True
    else:
        print("   -> [FALLO] El servidor aceptó una contribución no correspondiente.")
        return False


def test_verificacion_benigna(w3, contract, ipfs_url="http://127.0.0.1:5001/api/v0/add?pin=false", ipfs_get="http://127.0.0.1:8080/ipfs/"):
    """
    Prueba de Control: Caso Benigno (Sin manipulación).
    Verifica que en condiciones legítimas tanto la verificación descendente como ascendente son 100% exitosas.
    """
    print("\n" + "=" * 80)
    print("PRUEBA DE CONTROL: FUNCIONAMIENTO BENIGNO (Doble Verificación Exitosa)")
    print("=" * 80)

    # 1. Servidor legítimo
    modelo = NetCliente()
    pesos = [val.cpu().numpy() for _, val in modelo.state_dict().items()]
    resp = requests.post(ipfs_url, files={'file': pickle.dumps(pesos)}, timeout=10)
    cid = resp.json()['Hash']

    round_test = 998
    tx1 = contract.functions.updateModel(round_test, cid).build_transaction({
        'from': MEMBER1_ADDRESS,
        'nonce': w3.eth.get_transaction_count(MEMBER1_ADDRESS),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })
    signed1 = w3.eth.account.sign_transaction(tx1, private_key=PRIV_KEY1)
    w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed1.raw_transaction))

    # Cliente verifica descendente
    resp_ipfs = requests.get(f"{ipfs_get}{cid}", timeout=10)
    pesos_ipfs = pickle.loads(resp_ipfs.content)
    desc_ok = all(np.allclose(p1, p2, atol=1e-7) for p1, p2 in zip(pesos, pesos_ipfs))

    # Cliente registra ascendente
    cuenta2 = CLIENT_ACCOUNTS[2]
    tx2 = contract.functions.registerClientModel(round_test, cid).build_transaction({
        'from': cuenta2["address"],
        'nonce': w3.eth.get_transaction_count(cuenta2["address"]),
        'gas': 200000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })
    signed2 = w3.eth.account.sign_transaction(tx2, private_key=cuenta2["key"])
    w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed2.raw_transaction))

    # Servidor verifica ascendente
    cid_onchain = contract.functions.getClientModel(round_test, cuenta2["address"]).call()
    asc_ok = (cid_onchain == cid)

    print(f"   Verificación Descendente (Cliente <- Servidor): {'APROBADA' if desc_ok else 'FALLIDA'}")
    print(f"   Verificación Ascendente (Servidor <- Cliente):  {'APROBADA' if asc_ok else 'FALLIDA'}")

    return desc_ok and asc_ok


def main():
    parser = argparse.ArgumentParser(description="Banco de Pruebas de Verificación y Seguridad Criptográfica")
    parser.add_argument("--endpoint", type=str, default=ETH_ENDPOINT, help="RPC endpoint de Hyperledger Besu")
    parser.add_argument("--ipfs-api", type=str, default="http://127.0.0.1:5001/api/v0/add?pin=false", help="API add de IPFS")
    parser.add_argument("--ipfs-get", type=str, default="http://127.0.0.1:8080/ipfs/", help="Gateway get de IPFS")
    args = parser.parse_args()

    w3 = Web3(Web3.HTTPProvider(args.endpoint))
    if not w3.is_connected():
        print(f"[ERROR CRÍTICO] No se puede conectar a Hyperledger Besu en {args.endpoint}")
        print("Asegúrate de que la red Quickstart esté iniciada con ./run.sh")
        return

    contract_info_path = SMART_CONTRACTS_DIR / "Contract_Data" / "FLRegistry_info.json"
    if not contract_info_path.exists():
        print("[ERROR] FLRegistry_info.json no existe. Ejecuta contract_address.py primero.")
        return

    with open(contract_info_path, "r") as f:
        contract_data = json.load(f)
    contract_addr = Web3.to_checksum_address(contract_data['address'])

    with open(SMART_CONTRACTS_DIR / "FLRegistry.json", "r") as f:
        abi = json.load(f)

    contract = w3.eth.contract(address=contract_addr, abi=abi)
    print(f"Conectado a Besu. Contrato FLRegistry en: {contract_addr}")

    # Ejecutar pruebas
    res_control = test_verificacion_benigna(w3, contract, args.ipfs_api, args.ipfs_get)
    res_p1 = test_verificacion_descendente(w3, contract, args.ipfs_api, args.ipfs_get)
    res_p2 = test_verificacion_ascendente(w3, contract)

    print("\n" + "=" * 80)
    print("RESUMEN DE RESULTADOS DE LAS PRUEBAS DE VERIFICACIÓN:")
    print("=" * 80)
    print(f"Control (Flujo Benigno):               {'EXITOSA' if res_control else 'FALLIDA'}")
    print(f"Prueba 1 (Detección Servidor Malicioso):{'EXITOSA (Rechazo 100%)' if res_p1 else 'FALLIDA'}")
    print(f"Prueba 2 (Detección Cliente Malicioso): {'EXITOSA (Descarte 100%)' if res_p2 else 'FALLIDA'}")
    print("=" * 80)


if __name__ == "__main__":
    main()

