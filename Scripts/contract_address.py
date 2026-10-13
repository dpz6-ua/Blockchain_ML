import json
import argparse
from pathlib import Path
from web3 import Web3
from solcx import compile_standard, install_solc

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SMART_CONTRACTS_DIR = PROJECT_DIR / "Smart_Contracts"
CONTRACT_DATA_DIR = SMART_CONTRACTS_DIR / "Contract_Data"
CONTRACT_DATA_DIR.mkdir(parents=True, exist_ok=True)

member1_address = Web3.to_checksum_address("0xfe3b557e8fb62b89f4916b721be55ceb828dbd73")
priv_key1 = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

sol_file = SMART_CONTRACTS_DIR / "FLRegistry.sol"
output_info = CONTRACT_DATA_DIR / "FLRegistry_info.json"


def deploy_contract(eth_endpoint='http://localhost:18545'):
    w3 = Web3(Web3.HTTPProvider(eth_endpoint))
    if not w3.is_connected():
        print(f"Error: No se pudo conectar a Besu en {eth_endpoint}")
        return False

    print(f"Conectado a Besu en {eth_endpoint}")
    print(f"Compilando {sol_file}...")
    install_solc("0.8.10")

    with open(sol_file, "r") as file:
        contract_source_code = file.read()

    compiled_sol = compile_standard({
        "language": "Solidity",
        "sources": {"FLRegistry.sol": {"content": contract_source_code}},
        "settings": {"outputSelection": {"*": {"*": ["abi", "evm.bytecode", "metadata"]}}},
    }, solc_version="0.8.10")

    bytecode = compiled_sol["contracts"]["FLRegistry.sol"]["FLRegistry"]["evm"]["bytecode"]["object"]
    abi = compiled_sol["contracts"]["FLRegistry.sol"]["FLRegistry"]["abi"]

    print(f"Desplegando desde cuenta: {member1_address}")
    fl_registry = w3.eth.contract(abi=abi, bytecode=bytecode)

    transaction = fl_registry.constructor().build_transaction({
        'from': member1_address,
        'nonce': w3.eth.get_transaction_count(member1_address),
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })

    signed_tx = w3.eth.account.sign_transaction(transaction, priv_key1)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Transacción enviada: {tx_hash.hex()}. Esperando confirmación...")

    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print("\n" + "=" * 50)
    print("Contrato FLRegistry desplegado con éxito")
    print(f"Dirección del contrato: {tx_receipt.contractAddress}")
    print(f"Bloque de inclusión: {tx_receipt.blockNumber}")
    print(f"Gas consumido: {tx_receipt.gasUsed}")
    print("=" * 50)

    with open(output_info, "w") as f:
        json.dump({"address": tx_receipt.contractAddress, "abi": abi}, f, indent=2)
    print(f"\nInformación guardada en: {output_info}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Despliegue de FLRegistry en Hyperledger Besu")
    parser.add_argument("--endpoint", type=str, default="http://localhost:18545", help="Endpoint RPC de Besu")
    args = parser.parse_args()

    deploy_contract(args.endpoint)