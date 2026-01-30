import json
from web3 import Web3
from solcx import compile_standard, install_solc

ETH_ENDPOINT = 'http://localhost:18545' # EthSignerProxy/RPC
w3 = Web3(Web3.HTTPProvider(ETH_ENDPOINT))

member1_address = Web3.to_checksum_address("0xfe3b557e8fb62b89f4916b721be55ceb828dbd73")
priv_key1 = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

# Compilación del contrato FLRegistry
install_solc("0.8.10")
with open("../Smart_Contracts/FLRegistry.sol", "r") as file:
    contract_source_code = file.read()

compiled_sol = compile_standard({
    "language": "Solidity",
    "sources": {"../Smart_Contracts/FLRegistry.sol": {"content": contract_source_code}},
    "settings": {"outputSelection": {"*": {"*": ["abi", "evm.bytecode", "metadata"]}}},
}, solc_version="0.8.10")

bytecode = compiled_sol["contracts"]["../Smart_Contracts/FLRegistry.sol"]["FLRegistry"]["evm"]["bytecode"]["object"]
abi = compiled_sol["contracts"]["../Smart_Contracts/FLRegistry.sol"]["FLRegistry"]["abi"]


def deploy_contract():
    print(f"Despliegue desde nodo: {member1_address}")
    
    FLRegistry = w3.eth.contract(abi=abi, bytecode=bytecode)

    transaction = FLRegistry.constructor().build_transaction({
        'from': member1_address,
        'nonce': w3.eth.get_transaction_count(member1_address),
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })

    signed_tx = w3.eth.account.sign_transaction(transaction, priv_key1)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Transacción enviada: {tx_hash.hex()}. Esperando confirmación")
    
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    print("\n" + "="*40)
    print(f"Contrato desplegado")
    print(f"Dirección: {tx_receipt.contractAddress}")
    print("="*40)
    
    with open("../Smart_Contracts/Contract_Data/FLRegistry_info.json", "w") as f:
        json.dump({"address": tx_receipt.contractAddress, "abi": abi}, f)
    print("\nInformación guardada en 'Contract_Data/FLRegistry_info.json'")

if __name__ == "__main__":
    if w3.is_connected():
        deploy_contract()
    else:
        print("Error: No se pudo conectar a Besu en el puerto 18545")