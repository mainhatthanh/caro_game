"""Zobrist hashing and transposition table for Caro game AI."""

import random

from constants import BOARD_SIZE, EMPTY, PLAYER, AI

# Expose these so tests can clear state
transposition_table = {}

# Zobrist hash table: zobrist_table[row][col][player]
# player is PLAYER=1 or AI=-1, normalized to index 0/1
zobrist_table = None
SIDE_TO_MOVE = None

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2


def init_zobrist():
    global zobrist_table, SIDE_TO_MOVE
    rng = random.Random(123456789)
    zobrist_table = [[{PLAYER: 0, AI: 0} for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            zobrist_table[row][col][PLAYER] = rng.getrandbits(64)
            zobrist_table[row][col][AI] = rng.getrandbits(64)
    SIDE_TO_MOVE = rng.getrandbits(64)


def compute_zobrist(board):
    """Compute initial Zobrist hash from a board."""
    if zobrist_table is None:
        init_zobrist()
    h = 0
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            cell = board[row][col]
            if cell != EMPTY:
                h ^= zobrist_table[row][col][cell]
    return h


def update_zobrist(h, row, col, old_val, new_val):
    """Update hash when cell changes from old_val to new_val."""
    if zobrist_table is None:
        init_zobrist()
    if old_val != EMPTY:
        h ^= zobrist_table[row][col][old_val]
    if new_val != EMPTY:
        h ^= zobrist_table[row][col][new_val]
    return h


def toggle_side(h):
    """XOR the side-to-move bit."""
    if SIDE_TO_MOVE is None:
        init_zobrist()
    return h ^ SIDE_TO_MOVE


def tt_probe(h, depth, alpha, beta):
    """Probe transposition table.
    Returns (found, score, best_move).
    found: True if entry can be used for cutoff.
    """
    entry = transposition_table.get(h)
    if entry is None:
        return False, 0, None
    if entry["depth"] < depth:
        return False, 0, entry.get("best_move")
    if entry["flag"] == EXACT:
        return True, entry["score"], entry.get("best_move")
    if entry["flag"] == LOWERBOUND and entry["score"] >= beta:
        return True, entry["score"], entry.get("best_move")
    if entry["flag"] == UPPERBOUND and entry["score"] <= alpha:
        return True, entry["score"], entry.get("best_move")
    return False, 0, entry.get("best_move")


def tt_store(h, depth, score, flag, best_move=None):
    """Store an entry in the transposition table."""
    transposition_table[h] = {
        "depth": depth,
        "score": score,
        "flag": flag,
        "best_move": best_move,
    }


def tt_clear():
    """Clear the transposition table (e.g., between games)."""
    transposition_table.clear()
