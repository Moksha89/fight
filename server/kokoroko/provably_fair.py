"""
Provably Fair System — Hash-based verification for virtual dice games.

Flow:
  1. Before round: Generate server_seed, compute commitment_hash = SHA256(server_seed)
  2. Show commitment_hash to users (proves seed existed before bets)
  3. After round: Reveal server_seed + client_seed + nonce → derive dice result
  4. Anyone can verify: SHA256(server_seed) == commitment_hash
  5. Result: derive_dice_result(server_seed, client_seed, nonce) matches shown result

This prevents the server from changing results after bets are placed.
"""

import hashlib
import hmac
import secrets


def generate_server_seed():
    """Generate a cryptographically secure random server seed (64 hex chars)."""
    return secrets.token_hex(32)


def generate_client_seed():
    """Generate a client seed. In production, the client can provide their own."""
    return secrets.token_hex(16)


def compute_commitment_hash(server_seed):
    """
    Compute the commitment hash shown to users BEFORE the round.
    Users can later verify: SHA256(revealed_server_seed) == commitment_hash.
    """
    return hashlib.sha256(server_seed.encode()).hexdigest()


def derive_dice_result(server_seed, client_seed, nonce, num_dice=6, faces=6):
    """
    Deterministically derive dice results from seeds.

    Uses HMAC-SHA256(server_seed, client_seed:nonce) to generate a hash,
    then extracts dice values from sequential bytes.

    Args:
        server_seed: Secret server seed (revealed after round)
        client_seed: Public client seed (can be user-provided)
        nonce: Round number / counter (ensures uniqueness across rounds)
        num_dice: Number of dice to roll (default 6)
        faces: Number of faces per die (default 6)

    Returns:
        list[int]: Dice values (1-indexed, e.g. [1,3,5,2,6,4])
    """
    message = f"{client_seed}:{nonce}"
    h = hmac.new(server_seed.encode(), message.encode(), hashlib.sha256).hexdigest()

    dice = []
    for i in range(num_dice):
        # Take 8 hex chars (32 bits) per die for uniform distribution
        hex_chunk = h[i * 8: (i + 1) * 8]
        value = int(hex_chunk, 16)
        die_value = (value % faces) + 1
        dice.append(die_value)

    return dice


def verify_round(server_seed, commitment_hash, client_seed, nonce, expected_dice):
    """
    Verify a completed round:
    1. Check SHA256(server_seed) == commitment_hash
    2. Check derive_dice_result(server_seed, client_seed, nonce) == expected_dice

    Returns:
        dict: {valid: bool, seed_matches: bool, result_matches: bool, details: str}
    """
    seed_matches = compute_commitment_hash(server_seed) == commitment_hash
    derived = derive_dice_result(server_seed, client_seed, nonce)
    result_matches = derived == expected_dice

    valid = seed_matches and result_matches
    details = []
    if not seed_matches:
        details.append("Server seed hash does not match commitment")
    if not result_matches:
        details.append(f"Derived result {derived} does not match expected {expected_dice}")

    return {
        "valid": valid,
        "seed_matches": seed_matches,
        "result_matches": result_matches,
        "derived_result": derived,
        "details": "; ".join(details) if details else "Round verified successfully",
    }


def create_round_seeds(nonce):
    """
    Create all seeds for a new round.
    Returns dict with server_seed, client_seed, nonce, commitment_hash.
    """
    server_seed = generate_server_seed()
    client_seed = generate_client_seed()
    commitment_hash = compute_commitment_hash(server_seed)

    return {
        "server_seed": server_seed,
        "client_seed": client_seed,
        "nonce": nonce,
        "commitment_hash": commitment_hash,
    }
