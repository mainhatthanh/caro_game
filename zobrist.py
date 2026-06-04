"""Zobrist hashing and transposition table for the Caro AI.

Zobrist hashing maps board positions to 64-bit hash values using XOR.
Each (cell, player) pair gets a unique random 64-bit value. The board
hash is the XOR of all occupied cells' values. Because XOR is its own
inverse, placing or removing a stone is O(1): just XOR the cell's value.

The transposition table stores evaluated positions to avoid re-searching
them in different branches of the minimax tree. Uses depth-preferred
replacement: when two paths reach the same position, we keep the one
searched to a greater depth.
"""

import random

from constants import BOARD_SIZE, EMPTY, PLAYER, AI, TT_SIZE_LIMIT

# Global transposition table: hash -> {depth, score, flag, best_move, age}
transposition_table = {}

# Zobrist table: zobrist_table[row][col][player] = 64-bit random int
# Indexed by player value (PLAYER=1 or AI=-1, normalized to 0/1 internally)
zobrist_table = None
SIDE_TO_MOVE = None
tt_age = 0  # incremented each search, used for depth-preferred replacement

# TT entry flags for alpha-beta pruning states
EXACT = 0       # Exact evaluation (within [alpha, beta])
LOWERBOUND = 1  # Score is a lower bound (failed low — <= alpha)
UPPERBOUND = 2  # Score is an upper bound (failed high — >= beta)


def init_zobrist():
    """Initialize the Zobrist hash tables with deterministic random values.

    Uses a fixed seed (123456789) so hashes are reproducible across runs.
    Each of the 15x15x2 (cell, player) pairs gets a 64-bit random value.
    """
    global zobrist_table, SIDE_TO_MOVE
    rng = random.Random(123456789)
    zobrist_table = [[{PLAYER: 0, AI: 0} for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            zobrist_table[row][col][PLAYER] = rng.getrandbits(64)
            zobrist_table[row][col][AI] = rng.getrandbits(64)
    SIDE_TO_MOVE = rng.getrandbits(64)


def compute_zobrist(board):
    """Compute the Zobrist hash of a full board state.

    XORs together the values for all occupied cells.
    This is O(n²) but only called once per search (the root position).
    All subsequent updates use update_zobrist() which is O(1).
    """
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
    """Update hash incrementally when cell changes from old_val to new_val.

    XOR removes the old value (XORing twice cancels out) then adds the new.
    This is O(1) and is called at every node of the search tree.
    """
    if zobrist_table is None:
        init_zobrist()
    if old_val != EMPTY:
        h ^= zobrist_table[row][col][old_val]
    if new_val != EMPTY:
        h ^= zobrist_table[row][col][new_val]
    return h


def toggle_side(h):
    """XOR the side-to-move bit to indicate the opponent is to move."""
    if SIDE_TO_MOVE is None:
        init_zobrist()
    return h ^ SIDE_TO_MOVE


def tt_probe(h, depth, alpha, beta):
    """Probe the transposition table for hash `h`.

    Returns (found, score, best_move):
    - found=True: the entry can be used for a cutoff
    - found=False: no useful entry found, but best_move may still be valid
      as a hint for move ordering

    Uses the standard TT flag logic:
    - EXACT: return score directly
    - LOWERBOUND (score >= beta): fail high — return score
    - UPPERBOUND (score <= alpha): fail low — return score
    - Otherwise: entry exists but not deep enough for cutoff, return best_move hint
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


def tt_new_search():
    """Call at the start of each new search to increment age.

    Age is used by tt_store for replacement decisions — newer entries
    can replace older ones at the same depth, and eviction prefers
    old shallow entries.
    """
    global tt_age
    tt_age += 1


def tt_store(h, depth, score, flag, best_move=None):
    """Store an entry in the transposition table.

    Depth-preferred replacement: if the table already has a deeper entry
    for this position, we keep the deeper one (unless the new entry is
    EXACT — exact evaluations always override because they're more reliable
    than bounds).

    When the table exceeds TT_SIZE_LIMIT, _tt_evict() removes low-depth
    entries to make room.
    """
    if len(transposition_table) >= TT_SIZE_LIMIT:
        _tt_evict()
    existing = transposition_table.get(h)
    if existing is not None and existing["depth"] > depth:
        # Keep the deeper entry — skip shallow replace UNLESS new entry is EXACT
        if flag != EXACT or existing["flag"] == EXACT:
            return
    transposition_table[h] = {
        "depth": depth,
        "score": score,
        "flag": flag,
        "best_move": best_move,
        "age": tt_age,
    }


def _tt_evict():
    """Evict low-depth entries when the transposition table is full.

    Uses random sampling to avoid O(n) full scan. Samples 10,000 entries
    (or 25% of the table, whichever is smaller) and removes the one with
    the lowest search depth. This keeps the table near capacity while
    preferring to keep deep-search entries.

    Only evicts when the table is at least 50% full.
    """
    import random as _random
    keys = list(transposition_table.keys())
    if len(keys) < TT_SIZE_LIMIT // 2:
        return
    sample = _random.sample(keys, min(10000, len(keys) // 4))
    worst = min(sample, key=lambda k: transposition_table[k]["depth"])
    del transposition_table[worst]


def tt_clear():
    """Clear the transposition table entirely.

    Used between games in the simulation to prevent stale data from
    one game affecting another.
    """
    transposition_table.clear()
