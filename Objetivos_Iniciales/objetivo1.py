from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

ETH_ENDPOINT =  'http://localhost:18545'
w3 = Web3(Web3.HTTPProvider(ETH_ENDPOINT))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

if w3.is_connected():
    print(f"Conexión exitosa con {ETH_ENDPOINT}")
    print(f"Bloque actual: {w3.eth.block_number}")
else:
    print("no hay conexión")

accounts = w3.eth.accounts
print(f"Accounts num: {len(accounts)}")
if accounts:
    address = accounts[0]
    wei = w3.eth.get_balance(address)
    eth = w3.from_wei(wei, 'ether')
    print(f"Cuenta 0 address: {address}")
    print(f"Saldo en cuenta: {wei} wei y {eth} eth")
else:
    print("no hay cuentas registradas")


member1 = Web3.to_checksum_address("0xfe3b557e8fb62b89f4916b721be55ceb828dbd73")
priv_key1 = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

wei = w3.eth.get_balance(member1)
eth = w3.from_wei(wei, 'ether')
print(f"Saldo en member1: {wei} wei y {eth} eth")

new_account = w3.eth.account.create()    #Nueva cuenta
destinatario = Web3.to_checksum_address(new_account.address)

transaccion = {
    #'from': member1,
    'to': destinatario,
    'value': 10000,
    'gas': 21000,
    'gasPrice': w3.eth.gas_price,
    'nonce': w3.eth.get_transaction_count(member1),
    'chainId': w3.eth.chain_id
}

tx_hash = w3.eth.account.sign_transaction(transaccion, priv_key1)
signed_tx = w3.eth.send_raw_transaction(tx_hash.raw_transaction)
print(f"Hash de la transacción: {signed_tx.hex()}")
