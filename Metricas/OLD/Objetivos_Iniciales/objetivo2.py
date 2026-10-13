import json
from web3 import Web3
from web3.middleware import geth_poa_middleware

NODE_URL = "http://127.0.0.1:8545" 
CONTRACT_ADDRESS = "xxxxxxxxxxx"       # Dirección del FLRegistry

try:
    with open("FLRegistry_abi.json", "r") as f:
        CONTRACT_ABI = json.load(f)
except FileNotFoundError:
    print("Error: FLRegistry smart contract no existe")
    exit()

w3 = Web3(Web3.HTTPProvider(NODE_URL))
w3.middleware_onion.inject(geth_poa_middleware, layer=0) 
FLRegistry = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
print(f"Conexión establecida: {w3.is_connected()}")

def commitRound(round_id, model_hash, participants_list, clave_de_coordinador):
    
    coordinator_account = w3.eth.account.from_key(clave_de_coordinador)
    coordinator_address = coordinator_account.address
    
    transaction = FLRegistry.functions.commitRound(
        round_id,
        model_hash,
        participants_list
    ).build_transaction({
        'from': coordinator_address,
        'nonce': w3.eth.get_transaction_count(coordinator_address),
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })
    
    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=clave_de_coordinador)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    
    print(f"\nTransacción enviada con hash: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        print(f"Ronda {round_id} registrada en el bloque {receipt.blockNumber}.")
    else:
        print("Transacción fallida")
        
def verificarModelo(round_id, hash_modelo_recibido):
    try:
        registered_hash = FLRegistry.functions.getRoundHash(round_id).call()
        
        print(f"\n Verificación para la Ronda {round_id}:")
        print(f"Hash del modelo recibido: {hash_modelo_recibido}")
        print(f"Hash registrado en Blockchain: {registered_hash}")

        if registered_hash == hash_modelo_recibido:
            print("hash coincide. Modelo auténtico")
            return True
        else:
            print("hash no coincide. Modelo manipulado")
            return False

    except Exception as e:
        print(f"Error al leer la Blockchain: {e}")
        return False