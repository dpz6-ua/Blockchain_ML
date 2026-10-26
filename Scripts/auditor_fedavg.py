#!/usr/bin/env python3
"""
Auditor Ex-Post: Independent Verification of Federated Aggregation (FedAvg)
Connects to Hyperledger Besu and IPFS, retrieves client and server model commitments
for a given round, reconstructs the canonical FedAvg aggregation, and verifies whether
the server aggregated the global model faithfully without tampering.
"""

import time
import json
import pickle
import requests
import argparse
import numpy as np
from functools import reduce
from pathlib import Path
from web3 import Web3

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SMART_CONTRACTS_DIR = PROJECT_DIR / "Smart_Contracts"

ETH_ENDPOINT = "http://127.0.0.1:18545"
IPFS_GATEWAY = "http://127.0.0.1:8080/ipfs/"
IPFS_API = "http://127.0.0.1:5001/api/v0/add?pin=false"


def discover_participating_clients(contract, round_target: int) -> dict:
    """
    Discovers participating client addresses dynamically for round_target
    by querying ModelUpdated event logs emitted on Hyperledger Besu.
    """
    try:
        try:
            server_addr = contract.functions.serverAddress().call().lower()
        except Exception:
            server_addr = ""

        event_filter = contract.events.ModelUpdated.create_filter(from_block=0, to_block="latest")
        all_events = event_filter.get_all_entries()

        discovered = {}
        for ev in all_events:
            if ev.args.round == round_target:
                author = ev.args.author
                if author.lower() != server_addr and author not in discovered.values():
                    cid = contract.functions.getClientModel(round_target, Web3.to_checksum_address(author)).call()
                    if cid:
                        discovered[len(discovered) + 2] = Web3.to_checksum_address(author)

        if discovered:
            print(f"   [AUTODISCOVERY] {len(discovered)} client node(s) discovered dynamically from Besu event logs:")
            for cid_key, addr in discovered.items():
                print(f"      * Member {cid_key}: {addr}")
            return discovered
    except Exception as e:
        print(f"   [NOTICE] Event autodiscovery fallback ({e}). Using consortium registry.")

    return DEFAULT_CLIENTS


def audit_round(round_target: int, w3, contract, ipfs_get: str, ipfs_api: str, clients_dict: dict, samples_dict: dict, simulate_tampering: bool = False):
    print("\n" + "=" * 80)
    print("EX-POST FEDAVG AUDIT (Independent Verification of Aggregation Server)")
    print("=" * 80)
    print(f"Auditing Federated Round:    {round_target}")
    print(f"Besu Smart Contract:         {contract.address}")
    print(f"Participating Clients:       {len(clients_dict)} nodes")

    t_start = time.time()

    # 1. Query Besu on-chain commitments
    print("\n1. Querying Besu Smart Contract for Round", round_target, "commitments...")
    
    try:
        round_info = contract.functions.history(round_target).call()
        server_global_cid = round_info[1]
    except Exception as e:
        print(f"   [ERROR] Could not query server model for round {round_target}: {e}")
        return False

    if not server_global_cid:
        print(f"   [ERROR] No global model registered for round {round_target} on-chain.")
        return False

    print(f"   Server Global Model CID:  {server_global_cid}")

    client_cids = {}
    for member_id, addr in clients_dict.items():
        checksum_addr = Web3.to_checksum_address(addr)
        try:
            cid = contract.functions.getClientModel(round_target, checksum_addr).call()
            if not cid:
                print(f"   [WARNING] Client {member_id} ({addr[:10]}...) has NO registered CID for round {round_target}")
            else:
                client_cids[member_id] = cid
                n_samples = samples_dict.get(member_id, 1)
                print(f"   Client {member_id} ({addr[:10]}...): {cid} (weight: {n_samples} samples)")
        except Exception as e:
            print(f"   [ERROR] Failed reading client {member_id} on-chain: {e}")

    if len(client_cids) == 0:
        print("   [ERROR] No client commitments found for this round. Cannot reconstruct FedAvg.")
        return False

    # 2. Fetch weights from IPFS
    print(f"\n2. Fetching model updates from IPFS Gateway ({ipfs_get})...")
    client_weights = {}

    for member_id, cid in client_cids.items():
        url = f"{ipfs_get}{cid}"
        try:
            t_dl0 = time.time()
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"   [ERROR] Failed to download Client {member_id} model from {url} (status {resp.status_code})")
                return False
            weights = pickle.loads(resp.content)
            client_weights[member_id] = weights
            size_mb = len(resp.content) / (1024 * 1024)
            print(f"   Client {member_id}: {size_mb:.2f} MB downloaded in {time.time() - t_dl0:.3f}s [OK]")
        except Exception as e:
            print(f"   [ERROR] Error downloading Client {member_id} weights: {e}")
            return False

    # Download server global model
    url_server = f"{ipfs_get}{server_global_cid}"
    try:
        t_dl0 = time.time()
        resp_srv = requests.get(url_server, timeout=15)
        if resp_srv.status_code != 200:
            print(f"   [ERROR] Failed to download Server model from {url_server}")
            return False
        server_weights = pickle.loads(resp_srv.content)
        size_srv_mb = len(resp_srv.content) / (1024 * 1024)
        print(f"   Server Global Model: {size_srv_mb:.2f} MB downloaded in {time.time() - t_dl0:.3f}s [OK]")
    except Exception as e:
        print(f"   [ERROR] Error downloading server global model: {e}")
        return False

    if simulate_tampering:
        print("\n   [SIMULATION] Injecting artificial bias into server weights to demonstrate tampering detection...")
        server_weights = [arr.copy() + 0.1 for arr in server_weights]

    # 3. Independent FedAvg Re-aggregation
    print("\n3. Recomputing canonical FedAvg locally over downloaded client weights...")
    total_samples = sum(samples_dict.get(m, 1) for m in client_weights.keys())
    client_ids = list(client_weights.keys())
    
    # Replicate Flower's FedAvg aggregation directly in native dtype
    weighted_client_layers = [
        [layer * samples_dict.get(m, 1) for layer in client_weights[m]]
        for m in client_ids
    ]
    
    reconstructed_weights = [
        reduce(np.add, layer_updates) / total_samples
        for layer_updates in zip(*weighted_client_layers)
    ]

    # Optional: Upload reconstructed model to IPFS to check CID equality
    reconstructed_bytes = pickle.dumps(reconstructed_weights)
    reconstructed_cid = None
    try:
        resp_add = requests.post(ipfs_api, files={'file': reconstructed_bytes}, timeout=10)
        if resp_add.status_code == 200:
            reconstructed_cid = resp_add.json().get('Hash')
            print(f"   Reconstructed model CID generated via IPFS: {reconstructed_cid}")
    except Exception:
        pass

    # 4. Verification & Comparison
    print("\n4. Verifying reconstructed model against server global commitment on-chain...")
    
    # Layer-by-layer comparison
    layers_match = True
    max_layer_diff = 0.0
    TOLERANCE = 1e-6

    for l_idx, (w_rec, w_srv) in enumerate(zip(reconstructed_weights, server_weights)):
        diff = float(np.max(np.abs(w_rec - w_srv)))
        if diff > max_layer_diff:
            max_layer_diff = diff
        if not np.allclose(w_rec, w_srv, atol=TOLERANCE):
            layers_match = False
            print(f"   [DISCREPANCY] Layer {l_idx} differs by maximum delta: {diff:.6e}")
        else:
            print(f"   Layer {l_idx}: OK (delta: {diff:.6e})")

    t_total_audit = time.time() - t_start

    print(f"\nAudit Execution Latency:     {t_total_audit:.4f} seconds (Query + IPFS + FedAvg)")
    print(f"Maximum Parameter Delta:     {max_layer_diff:.6e} (tolerance: {TOLERANCE:.0e})")

    if reconstructed_cid and not simulate_tampering:
        cid_match = (reconstructed_cid == server_global_cid)
        print(f"CID Equality (Recon vs On-Chain): {'MATCH' if cid_match else 'MISMATCH'}")

    print("-" * 80)
    if layers_match:
        print(">> [AUDIT PASSED] VERIFIED FAITHFUL AGGREGATION")
        print("   The server correctly executed FedAvg on round", round_target, "without bias or tampering.")
        print("   Integrity proof verified against Hyperledger Besu & IPFS.")
        res = True
    else:
        print(">> [AUDIT FAILED] DISCREPANCY DETECTED: SERVER MALFEASANCE DETECTED")
        print("   The global model published on-chain does NOT match canonical FedAvg aggregation.")
        print("   Public, non-repudiable cryptographic proof of tampering is established.")
        res = False
    print("=" * 80 + "\n")
    return res


def main():
    parser = argparse.ArgumentParser(description="Ex-Post FedAvg Auditor for Hyperledger Besu + IPFS")
    parser.add_argument("--round", type=int, default=None, help="Round number to audit (default: latest round registered on Besu)")
    parser.add_argument("--endpoint", type=str, default=ETH_ENDPOINT, help="Hyperledger Besu RPC endpoint")
    parser.add_argument("--ipfs-get", type=str, default=IPFS_GATEWAY, help="IPFS Gateway URL (e.g. http://127.0.0.1:8080/ipfs/)")
    parser.add_argument("--ipfs-api", type=str, default=IPFS_API, help="IPFS API Add URL (e.g. http://127.0.0.1:5001/api/v0/add?pin=false)")
    parser.add_argument("--samples", type=str, default="equal", help="Sample count per client ('equal' for balanced 50%/50% FedAvg, or comma-separated numbers, default: equal)")
    parser.add_argument("--simulate-tampering", action="store_true", help="Simulate a Byzantine server that tampered with the weights")
    args = parser.parse_args()

    w3 = Web3(Web3.HTTPProvider(args.endpoint))
    if not w3.is_connected():
        print(f"[ERROR] Could not connect to Hyperledger Besu at {args.endpoint}")
        return

    contract_info_path = SMART_CONTRACTS_DIR / "Contract_Data" / "FLRegistry_info.json"
    if not contract_info_path.exists():
        print(f"[ERROR] {contract_info_path} not found. Deploy contract first.")
        return

    with open(contract_info_path, "r") as f:
        contract_data = json.load(f)
    contract_addr = Web3.to_checksum_address(contract_data["address"])

    with open(SMART_CONTRACTS_DIR / "FLRegistry.json", "r") as f:
        abi = json.load(f)

    contract = w3.eth.contract(address=contract_addr, abi=abi)

    # Determine round
    if args.round is not None:
        target_round = args.round
    else:
        try:
            target_round = contract.functions.latestRound().call()
            print(f"No round specified. Detected latest on-chain round: {target_round}")
        except Exception:
            target_round = 1

    # Discover participating clients dynamically from Besu event logs
    clients_dict = discover_participating_clients(contract, target_round)

    # Parse sample counts
    if args.samples == "equal" or not args.samples:
        samples_dict = {m: 1 for m in clients_dict.keys()}
    else:
        sample_list = [int(s.strip()) for s in args.samples.split(",")]
        samples_dict = {}
        for idx, m in enumerate(clients_dict.keys()):
            samples_dict[m] = sample_list[idx] if idx < len(sample_list) else 1

    audit_round(
        round_target=target_round,
        w3=w3,
        contract=contract,
        ipfs_get=args.ipfs_get,
        ipfs_api=args.ipfs_api,
        clients_dict=clients_dict,
        samples_dict=samples_dict,
        simulate_tampering=args.simulate_tampering
    )


if __name__ == "__main__":
    main()

