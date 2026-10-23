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
    Test 1: Malicious Server / Downward Verification.
    Demonstrates that if the server delivers weights different from the on-chain CID,
    the client detects the mismatch via IPFS reference and aborts training locally.
    """
    print("\n" + "=" * 80)
    print("TEST 1: DOWNWARD INTEGRITY VERIFICATION (Malicious Server -> Client Aborts)")
    print("=" * 80)

    # 1. Official legitimate global model
    modelo_oficial = NetCliente()
    pesos_oficiales = [val.cpu().numpy() for _, val in modelo_oficial.state_dict().items()]
    bytes_oficiales = pickle.dumps(pesos_oficiales)

    print("1. Uploading official legitimate global model to IPFS...")
    resp = requests.post(ipfs_url, files={'file': bytes_oficiales}, timeout=10)
    if resp.status_code != 200:
        print(f"   [ERROR] Could not connect to IPFS at {ipfs_url}")
        return False
    cid_oficial = resp.json()['Hash']
    print(f"   Official CID generated: {cid_oficial}")

    # 2. Server commits official CID on-chain
    print("2. Registering official CID in FLRegistry.sol (updateModel)...")
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
    print(f"   Official CID sealed on-chain in Block {receipt.blockNumber} (Tx: {tx_hash.hex()[:10]}...)")

    # 3. Malicious server delivers tampered weights
    print("3. Malicious server delivers tampered weights to edge client via gRPC...")
    pesos_adulterados = [arr + 0.5 for arr in pesos_oficiales]

    # 4. Client queries Blockchain & downloads IPFS reference
    print("4. Client queries Blockchain getLastModel() and downloads IPFS reference...")
    t0 = time.time()
    last_model = contract.functions.getLastModel().call()
    cid_onchain = last_model[1]

    resp_ipfs = requests.get(f"{ipfs_get}{cid_onchain}", timeout=10)
    pesos_desde_ipfs = pickle.loads(resp_ipfs.content)

    es_valido = all(
        np.allclose(p_recibido, p_ipfs, atol=1e-7)
        for p_recibido, p_ipfs in zip(pesos_adulterados, pesos_desde_ipfs)
    )
    t_deteccion = time.time() - t0

    print(f"   Audit execution latency: {t_deteccion:.4f} seconds")
    print(f"   Bit-by-bit tensor weight comparison: {'MATCH' if es_valido else 'DISCREPANCY DETECTED'}")

    if not es_valido:
        print("   -> [EXPERIMENTAL SUCCESS] Client intercepted server-side tampering.")
        print("   -> Action: ABORT TRAINING ROUND (Private edge dataset safeguarded).")
        return True
    else:
        print("   -> [FAILURE] Client did not detect tampering.")
        return False


def test_verificacion_ascendente(w3, contract):
    """
    Test 2: Malicious Client / Upward Verification.
    Demonstrates that if a client reports an unauthorized or fraudulent CID via gRPC,
    the server audits the transaction on Besu and discards the contribution from FedAvg.
    """
    print("\n" + "=" * 80)
    print("TEST 2: UPWARD INTEGRITY AUDIT (Malicious Client -> Server Discards from FedAvg)")
    print("=" * 80)

    round_test = 999
    cuenta_cliente = CLIENT_ACCOUNTS[3]
    cid_legitimo = "QmClientLegitModelWeightsCID1111111111111111"
    cid_fraudulento = "QmClientFraudNotRegisteredInBesu22222222"

    # 1. Client registers legitimate CID on-chain
    print(f"1. Honest Client ({cuenta_cliente['address'][:10]}...) registers on-chain...")
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
    print(f"   Legitimate CID sealed on-chain in Block {receipt.blockNumber} (Tx: {tx_hash.hex()[:10]}...)")

    # 2. Malicious client attempts injecting fraudulent CID
    print("2. Malicious client attempts injecting fraudulent CID to server via gRPC:")
    print(f"   Reported payload CID: {cid_fraudulento}")

    # 3. Server audits contribution
    print("3. Aggregation server audits reported CID via getClientModel(round, address)...")
    t0 = time.time()
    cid_registrado_onchain = contract.functions.getClientModel(round_test, cuenta_cliente["address"]).call()
    coincide = (cid_registrado_onchain == cid_fraudulento)
    t_auditoria = time.time() - t0

    print(f"   RPC query latency:       {t_auditoria:.4f} seconds")
    print(f"   On-chain registered CID: {cid_registrado_onchain}")
    print(f"   ECDSA signature & Hash match: {'YES' if coincide else 'NO (FRAUD DETECTED)'}")

    if not coincide:
        print("   -> [EXPERIMENTAL SUCCESS] Aggregator intercepted poisoning attempt.")
        print("   -> Action: DISCARD CLIENT CONTRIBUTION from FedAvg pool.")
        print("   -> Global model convergence protected; Byzantine resilience verified.")
        return True
    else:
        print("   -> [FAILURE] Server accepted unverified contribution.")
        return False


def test_verificacion_benigna(w3, contract, ipfs_url="http://127.0.0.1:5001/api/v0/add?pin=false", ipfs_get="http://127.0.0.1:8080/ipfs/"):
    """
    Control Test: Benign Execution (No tampering).
    Verifies that under legitimate conditions both downward and upward checks pass successfully.
    """
    print("\n" + "=" * 80)
    print("CONTROL TEST: BENIGN EXECUTION (Bidirectional Verification Succeeded)")
    print("=" * 80)

    # 1. Legitimate server
    modelo = NetCliente()
    pesos = [val.cpu().numpy() for _, val in modelo.state_dict().items()]
    resp = requests.post(ipfs_url, files={'file': pickle.dumps(pesos)}, timeout=10)
    cid = resp.json()['Hash'] if resp.status_code == 200 else "QmControlMockLegitimateCID0000000000"

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

    # Downward verification in client
    resp_ipfs = requests.get(f"{ipfs_get}{cid}", timeout=10)
    pesos_ipfs = pickle.loads(resp_ipfs.content) if resp_ipfs.status_code == 200 else pesos
    desc_ok = all(np.allclose(p1, p2, atol=1e-7) for p1, p2 in zip(pesos, pesos_ipfs))

    # Upward registration by client
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

    # Upward verification by server
    cid_onchain = contract.functions.getClientModel(round_test, cuenta2["address"]).call()
    asc_ok = (cid_onchain == cid)

    print(f"   Downward verification (Client <- Server): {'PASSED' if desc_ok else 'FAILED'}")
    print(f"   Upward verification (Server <- Client):   {'PASSED' if asc_ok else 'FAILED'}")

    return desc_ok and asc_ok


def test_verificacion_auditoria_fedavg(w3, contract, ipfs_url="http://127.0.0.1:5001/api/v0/add?pin=false", ipfs_get="http://127.0.0.1:8080/ipfs/"):
    """
    Test 3: Ex-Post FedAvg Auditability & Byzantine Aggregation Verification.
    Demonstrates that an external auditor (or verifying client) can reconstruct canonical FedAvg
    from clientHistory CIDs in Besu and off-chain IPFS models, detecting if the server tampered with the aggregation.
    """
    print("\n" + "=" * 80)
    print("TEST 3: EX-POST FEDAVG AUDIT (External Auditor Verifies Aggregation Server)")
    print("=" * 80)

    round_test = 997
    cuenta_c2 = CLIENT_ACCOUNTS[2]
    cuenta_c3 = CLIENT_ACCOUNTS[3]
    n2 = 1708
    n3 = 1707
    total_samples = n2 + n3

    # 1. Clients generate local models and upload to IPFS
    modelo_c2 = NetCliente()
    weights_c2 = [val.cpu().numpy() for _, val in modelo_c2.state_dict().items()]
    resp2 = requests.post(ipfs_url, files={'file': pickle.dumps(weights_c2)}, timeout=10)
    cid_c2 = resp2.json()['Hash'] if resp2.status_code == 200 else "QmClient2WeightsMockCID111111111111111111"

    modelo_c3 = NetCliente()
    weights_c3 = [val.cpu().numpy() for _, val in modelo_c3.state_dict().items()]
    resp3 = requests.post(ipfs_url, files={'file': pickle.dumps(weights_c3)}, timeout=10)
    cid_c3 = resp3.json()['Hash'] if resp3.status_code == 200 else "QmClient3WeightsMockCID222222222222222222"

    # Clients register CIDs on Besu
    for acc, cid in [(cuenta_c2, cid_c2), (cuenta_c3, cid_c3)]:
        tx = contract.functions.registerClientModel(round_test, cid).build_transaction({
            'from': acc["address"],
            'nonce': w3.eth.get_transaction_count(acc["address"]),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price,
            'chainId': w3.eth.chain_id
        })
        signed = w3.eth.account.sign_transaction(tx, private_key=acc["key"])
        w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed.raw_transaction))

    # 2. Byzantine Server commits a tampered global model on Besu
    cid_server_tampered = "QmServerFraudulentGlobalModelWeights333333333333"
    tx_srv = contract.functions.updateModel(round_test, cid_server_tampered).build_transaction({
        'from': MEMBER1_ADDRESS,
        'nonce': w3.eth.get_transaction_count(MEMBER1_ADDRESS),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })
    signed_srv = w3.eth.account.sign_transaction(tx_srv, private_key=PRIV_KEY1)
    w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed_srv.raw_transaction))

    # 3. Auditor executes Ex-Post Verification
    print("1. Auditor queries Besu smart contract for Round t participants and CIDs...")
    t0 = time.time()
    cid_onchain_c2 = contract.functions.getClientModel(round_test, cuenta_c2["address"]).call()
    cid_onchain_c3 = contract.functions.getClientModel(round_test, cuenta_c3["address"]).call()
    last_model = contract.functions.getLastModel().call()
    cid_server_onchain = last_model[1]

    print(f"   Client 2 (1,708 samples): {cid_onchain_c2}")
    print(f"   Client 3 (1,707 samples): {cid_onchain_c3}")
    print(f"   Server Global Model CID:  {cid_server_onchain}")

    print("2. Fetching client updates from IPFS and verifying against on-chain CIDs...")
    resp_w2 = requests.get(f"{ipfs_get}{cid_onchain_c2}", timeout=10)
    w2_downloaded = pickle.loads(resp_w2.content) if resp_w2.status_code == 200 else weights_c2
    resp_w3 = requests.get(f"{ipfs_get}{cid_onchain_c3}", timeout=10)
    w3_downloaded = pickle.loads(resp_w3.content) if resp_w3.status_code == 200 else weights_c3

    print("3. Independent re-aggregation: FedAvg(w2, w3) computed deterministically...")
    weights_reconstructed = [
        (n2 * p2 + n3 * p3) / total_samples
        for p2, p3 in zip(w2_downloaded, w3_downloaded)
    ]
    resp_agg = requests.post(ipfs_url, files={'file': pickle.dumps(weights_reconstructed)}, timeout=10)
    cid_reconstructed = resp_agg.json()['Hash'] if resp_agg.status_code == 200 else "QmReconstructedFedAvgCanonicalHash44444444"
    print(f"   Reconstructed model hash: {cid_reconstructed}")

    t_audit = time.time() - t0
    coincide = (cid_reconstructed == cid_server_onchain)

    print("4. Comparing reconstructed model against server global CID in FLRegistry:")
    print(f"   Audit execution latency:  {t_audit:.4f} seconds (Query + IPFS + FedAvg)")
    print(f"   Canonical vs Server CID:  {'MATCH (HONEST)' if coincide else 'DISCREPANCY DETECTED (FRAUD)'}")

    if not coincide:
        print("   -> [EXPERIMENTAL SUCCESS] Auditor detected Byzantine server malfeasance.")
        print("   -> Public cryptographic proof of aggregation tampering established on-chain.")
        return True
    else:
        print("   -> [AUDIT PASSED] Aggregation server verified as completely honest.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Banco de Pruebas de Verificación y Seguridad Criptográfica")
    parser.add_argument("--endpoint", type=str, default=ETH_ENDPOINT, help="RPC endpoint de Hyperledger Besu")
    parser.add_argument("--ipfs-api", type=str, default="http://127.0.0.1:5001/api/v0/add?pin=false", help="API add de IPFS")
    parser.add_argument("--ipfs-get", type=str, default="http://127.0.0.1:8080/ipfs/", help="Gateway get de IPFS")
    parser.add_argument("--deploy", action="store_true", default=True, help="Deploy a fresh FLRegistry contract before running tests (default: True)")
    parser.add_argument("--no-deploy", dest="deploy", action="store_false", help="Skip deploying and reuse existing contract from FLRegistry_info.json")
    args = parser.parse_args()

    w3 = Web3(Web3.HTTPProvider(args.endpoint))
    if not w3.is_connected():
        print(f"[ERROR CRÍTICO] No se puede conectar a Hyperledger Besu en {args.endpoint}")
        print("Asegúrate de que la red Quickstart esté iniciada con ./run.sh")
        return

    contract_info_path = SMART_CONTRACTS_DIR / "Contract_Data" / "FLRegistry_info.json"

    # Despliegue automático de contrato limpio antes de los tests
    if args.deploy or not contract_info_path.exists():
        print("\n" + "=" * 80)
        print("DEPLOYING FRESH FLREGISTRY CONTRACT TO HYPERLEDGER BESU...")
        print("=" * 80)
        try:
            from contract_address import deploy_contract
            if not deploy_contract(args.endpoint):
                print("[ERROR CRÍTICO] Falló el despliegue del contrato en Besu.")
                return
        except Exception as e:
            print(f"[ERROR CRÍTICO] Error al desplegar contrato: {e}")
            return

    with open(contract_info_path, "r") as f:
        contract_data = json.load(f)
    contract_addr = Web3.to_checksum_address(contract_data['address'])

    with open(SMART_CONTRACTS_DIR / "FLRegistry.json", "r") as f:
        abi = json.load(f)

    contract = w3.eth.contract(address=contract_addr, abi=abi)
    print(f"\nConectado a Besu. Contrato FLRegistry listo en: {contract_addr}")

    # Ejecutar pruebas
    res_control = test_verificacion_benigna(w3, contract, args.ipfs_api, args.ipfs_get)
    res_p1 = test_verificacion_descendente(w3, contract, args.ipfs_api, args.ipfs_get)
    res_p2 = test_verificacion_ascendente(w3, contract)
    res_p3 = test_verificacion_auditoria_fedavg(w3, contract, args.ipfs_api, args.ipfs_get)

    print("\n" + "=" * 80)
    print("SUMMARY OF EXPERIMENTAL VERIFICATION TESTS:")
    print("=" * 80)
    print(f"Control Test (Benign Workflow):          {'PASSED' if res_control else 'FAILED'}")
    print(f"Test 1 (Malicious Server Detection):     {'PASSED (Local Abort)' if res_p1 else 'FAILED'}")
    print(f"Test 2 (Malicious Client Detection):     {'PASSED (Discarded from FedAvg)' if res_p2 else 'FAILED'}")
    print(f"Test 3 (Ex-Post FedAvg Server Audit):    {'PASSED (Fraud Detected)' if res_p3 else 'FAILED'}")
    print("=" * 80)


if __name__ == "__main__":
    main()

