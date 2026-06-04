"""Caro AI engine — pre-search threat pipeline, alpha-beta minimax, iterative deepening.

Architecture (called in order):

1. find_best_move_by_minimax()  — entry point
   ├── find_immediate_winning_moves()  — Priority 1: AI wins, Priority 2: block opponent win
   └── Pre-search pipeline              — Priority 3-10: scan ALL candidates for threats
       ├── detect_fork()                — Compound threats (double-four, four-three, double-three)
       ├── find_single_axis_threat()    — Single-axis threats (open-four, semi-open-four, open-three)
       └── Attack vs Defense compare    — Lower priority = more urgent; defense wins if tied
   └── _iterative_deepening_search()   — Fallback: minimax with aspiration windows
       └── search_root_id()             — Root-level search at one depth
           └── _minimax()               — Alpha-beta with LMR, TT, candidate limiting
               └── _quiescence_search() — Threat extension at leaf nodes
"""

import random

from constants import (
    EMPTY, PLAYER, AI, WIN_SCORE, EASY, MEDIUM, MAX_DEPTH, BOARD_SIZE,
    FORK_NONE, FORK_DOUBLE_FOUR, FORK_FOUR_THREE, FORK_DOUBLE_THREE,
    THREAT_NONE, THREAT_FIVE, THREAT_OPEN_FOUR, THREAT_SEMI_OPEN_FOUR,
    THREAT_OPEN_THREE, THREAT_SEMI_OPEN_THREE,
    MOVE_PRIORITY_WIN, MOVE_PRIORITY_BLOCK_WIN, MOVE_PRIORITY_THREAT,
    MOVE_PRIORITY_BLOCK_THREAT, MOVE_PRIORITY_KILLER,
    ASPIRATION_WINDOW, LMR_DEPTH_THRESHOLD, LMR_MOVES_THRESHOLD, LMR_REDUCTION,
    CANDIDATE_LIMIT_DEPTH_EARLY, CANDIDATE_LIMIT_DEPTH_MID,
    CANDIDATE_LIMIT_EARLY, CANDIDATE_LIMIT_MID, CANDIDATE_LIMIT_DEEP,
)
from board import get_candidate_moves
from rules import check_winner, is_board_full, check_winner_fast
from evaluation import evaluate_board, compute_move_delta
from zobrist import (
    tt_probe, tt_store, tt_new_search, compute_zobrist, update_zobrist,
    EXACT, LOWERBOUND, UPPERBOUND,
)

# ---------------------------------------------------------------------------
# Search-global heuristics — preserved across calls in the same game
# ---------------------------------------------------------------------------
# Killer moves: per-depth list of recent beta-cutoff moves (max 2 per depth)
killer_moves = {d: [] for d in range(MAX_DEPTH + 1)}
# History heuristic: how often each cell caused a beta cutoff at each depth
history_score = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]

# ---------------------------------------------------------------------------
# Constants for fork detection
# ---------------------------------------------------------------------------
# 4 axes through any cell, each represented as (dr1, dc1, dr2, dc2) —
# a pair of opposite direction vectors for bidirectional scanning.
AXES = [
    (0, 1, 0, -1),    # horizontal: left, right
    (1, 0, -1, 0),    # vertical: down, up
    (1, 1, -1, -1),   # main diagonal ↘, ↖
    (1, -1, -1, 1),   # anti diagonal ↙, ↗
]


# =========================================================================
# SECTION 1: Axis classification
# =========================================================================

def classify_axis(board, row, col, player, dr1, dc1, dr2, dc2):
    """Classify the threat level on ONE axis through (row, col) for `player`.

    Scans in both directions from (row, col) along the axis:
    1. Count consecutive stones of `player` in each direction
    2. Check if the ends are open (EMPTY) or blocked (opponent/wall)
    3. Classify based on total count and open-end status

    Returns (threat_category, count) where threat_category is THREAT_*
    or THREAT_NONE. This is the foundation for both fork detection and
    single-axis threat detection.
    """
    n = BOARD_SIZE

    # Direction 1
    c1 = 1  # count including the placed cell at (row, col)
    i, j = row + dr1, col + dc1
    while 0 <= i < n and 0 <= j < n and board[i][j] == player:
        c1 += 1
        i += dr1
        j += dc1
    open1 = 0 <= i < n and 0 <= j < n and board[i][j] == EMPTY

    # Direction 2 (opposite direction)
    c2 = 1
    i, j = row + dr2, col + dc2
    while 0 <= i < n and 0 <= j < n and board[i][j] == player:
        c2 += 1
        i += dr2
        j += dc2
    open2 = 0 <= i < n and 0 <= j < n and board[i][j] == EMPTY

    total = c1 + c2 - 1  # don't double-count the placed cell

    if total >= 5:
        return THREAT_FIVE, total

    both_open = open1 and open2
    one_open = open1 != open2

    if total == 4:
        if both_open:
            return THREAT_OPEN_FOUR, total      # .MMMM. — can win next move
        elif one_open:
            return THREAT_SEMI_OPEN_FOUR, total  # EMMMM. or .MMMME — threat
        return THREAT_NONE, total                # #MMMM# — dead, both blocked

    if total == 3:
        if both_open:
            return THREAT_OPEN_THREE, total      # .MMM. — can be extended to four
        elif one_open:
            return THREAT_SEMI_OPEN_THREE, total # EMMM. or .MMME — limited threat
        return THREAT_NONE, total

    return THREAT_NONE, total


# =========================================================================
# SECTION 2: Single-axis threat detection
# =========================================================================

def find_single_axis_threat(board, row, col, player):
    """Check if placing `player` at (row, col) creates a strong single-axis threat.

    Unlike detect_fork() which looks for compound threats across multiple axes,
    this catches the case where a single axis has a strong pattern:
      - open-four (winning)
      - semi-open-four (one more move to win)
      - open-three (extendable to four)

    Without this check, single-axis threats fall through to the main search
    which may not see them at shallow depths (classic horizon effect:
    the opponent's response to the threat is at depth+1 and the search stops).

    Returns (THREAT_*_* , total_count) or (THREAT_NONE, None).
    """
    worst = (THREAT_NONE, None)
    rank = {THREAT_NONE: 0, THREAT_OPEN_THREE: 1, THREAT_SEMI_OPEN_THREE: 2,
            THREAT_SEMI_OPEN_FOUR: 3, THREAT_OPEN_FOUR: 4, THREAT_FIVE: 5}
    for dr1, dc1, dr2, dc2 in AXES:
        cat, total = classify_axis(board, row, col, player, dr1, dc1, dr2, dc2)
        if rank.get(cat, 0) > rank.get(worst[0], 0):
            worst = (cat, total)
    return worst


# =========================================================================
# SECTION 3: Fork detection
# =========================================================================

def detect_fork(board, row, col, player):
    """Detect if placing `player` at (row, col) creates a compound threat (fork).

    A fork means the player has strong threats on 2+ different axes, making it
    impossible for the opponent to block all of them. Scans all 4 axes using
    classify_axis() and combines them:

    - double-four: 2+ axes with open or semi-open four — unstoppable
    - four-three: 1 four-axis + 1 three-axis — nearly unstoppable
    - double-three: 2+ axes with open or semi-open three — very dangerous

    Semi-open threats are included because a semi-open-four on one axis plus
    an open-three on another is still a forced win (opponent can block one
    but not the other).
    """
    counts = {THREAT_FIVE: 0, THREAT_OPEN_FOUR: 0, THREAT_SEMI_OPEN_FOUR: 0,
              THREAT_OPEN_THREE: 0, THREAT_SEMI_OPEN_THREE: 0}

    for dr1, dc1, dr2, dc2 in AXES:
        cat, _total = classify_axis(board, row, col, player, dr1, dc1, dr2, dc2)
        if cat in counts:
            counts[cat] += 1

    if counts[THREAT_FIVE] >= 1:
        return FORK_DOUBLE_FOUR  # treated as winning

    # Combine open and semi-open counts — both contribute to forks
    open_fours = counts[THREAT_OPEN_FOUR] + counts[THREAT_SEMI_OPEN_FOUR]
    open_threes = counts[THREAT_OPEN_THREE] + counts[THREAT_SEMI_OPEN_THREE]

    if open_fours >= 2:
        return FORK_DOUBLE_FOUR

    if open_fours >= 1 and open_threes >= 1:
        return FORK_FOUR_THREE

    if open_threes >= 2:
        return FORK_DOUBLE_THREE

    return FORK_NONE


# =========================================================================
# SECTION 4: Immediate win/block detection
# =========================================================================

def find_immediate_winning_moves(board, player):
    """Return all empty cells where placing `player` stone wins immediately.

    Scans all candidates, temporarily places `player`, and checks for 5+ in a row.
    This is the highest priority in the pre-search pipeline: if AI can win, it wins.
    If opponent can win, AI must block.
    """
    winning_moves = []
    candidate_moves = get_candidate_moves(board, distance=1)

    for row, col in candidate_moves:
        board[row][col] = player
        if check_winner_fast(board, player, (row, col)):
            winning_moves.append((row, col))
        board[row][col] = EMPTY

    return winning_moves


# =========================================================================
# SECTION 5: Move ordering
# =========================================================================

def evaluate_for_ordering_move(board, row, col, player, depth, opponent=None):
    """Score a candidate move for ordering purposes (higher = search first).

    Components (from highest to lowest weight):
    1. Immediate win (MOVE_PRIORITY_WIN = 10^9)
    2. Block opponent win (MOVE_PRIORITY_BLOCK_WIN = 2*10^8)
    3. Threat bonus (open-four, semi-open-four, open-three)
    4. Block bonus (opponent threat at this cell)
    5. Killer move bonus (beta cutoff in sibling nodes at same depth)
    6. History heuristic (frequency of beta cutoffs at this cell)
    7. Neighbor density (proximity to other stones — good positions)
    8. Center bonus (prefer central positions for tactical flexibility)
    """
    move = (row, col)
    killer_bonus = MOVE_PRIORITY_KILLER if move in killer_moves.get(depth, []) else 0
    opp = AI if player == PLAYER else PLAYER if opponent is None else opponent

    # ---- Threat bonus: place player stone and check threats created ----
    board[row][col] = player
    if check_winner_fast(board, player, (row, col)):
        board[row][col] = EMPTY
        return MOVE_PRIORITY_WIN + killer_bonus + history_score[row][col]

    threat_bonus = 0
    for dr1, dc1, dr2, dc2 in AXES:
        cat, _ = classify_axis(board, row, col, player, dr1, dc1, dr2, dc2)
        if cat in (THREAT_OPEN_FOUR,):
            threat_bonus = max(threat_bonus, MOVE_PRIORITY_THREAT * 10)
        elif cat in (THREAT_SEMI_OPEN_FOUR, THREAT_OPEN_THREE):
            threat_bonus = max(threat_bonus, MOVE_PRIORITY_THREAT)
    board[row][col] = EMPTY

    # ---- Block bonus: place opponent stone and check threats created ----
    board[row][col] = opp
    block_bonus = 0
    for dr1, dc1, dr2, dc2 in AXES:
        cat, _ = classify_axis(board, row, col, opp, dr1, dc1, dr2, dc2)
        if cat in (THREAT_OPEN_FOUR,):
            block_bonus = max(block_bonus, MOVE_PRIORITY_BLOCK_THREAT * 10)
        elif cat in (THREAT_SEMI_OPEN_FOUR, THREAT_OPEN_THREE):
            block_bonus = max(block_bonus, MOVE_PRIORITY_BLOCK_THREAT)
    board[row][col] = EMPTY

    # ---- Positional bonus: neighbor counts and center proximity ----
    ally_neighbors = 0
    opponent_neighbors = 0
    center = BOARD_SIZE // 2

    for dr in range(-1, 2):
        for dc in range(-1, 2):
            if dr == 0 and dc == 0:
                continue
            nr = row + dr
            nc = col + dc
            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
                if board[nr][nc] == player:
                    ally_neighbors += 1
                elif board[nr][nc] != EMPTY:
                    opponent_neighbors += 1

    center_bonus = max(0, center - abs(row - center) - abs(col - center))
    return (killer_bonus + threat_bonus + block_bonus + ally_neighbors * 10
            + opponent_neighbors * 6 + center_bonus + history_score[row][col])


def order_moves(board, candidate_moves, player, depth, hash_move=None, opponent=None):
    """Sort candidate moves by priority (highest priority first).

    TT hash move gets a massive bonus (10^9) so it's always searched first
    if available. This significantly improves pruning because the TT move
    from a deeper search is likely the best move at this position too.
    """
    opp = AI if player == PLAYER else PLAYER if opponent is None else opponent
    scored_moves = []

    for row, col in candidate_moves:
        s = evaluate_for_ordering_move(board, row, col, player, depth, opp)
        if hash_move and (row, col) == hash_move:
            s += 10**9
        scored_moves.append(((row, col), s))

    scored_moves.sort(key=lambda x: x[1], reverse=True)
    ordered_moves = [move for move, score in scored_moves]
    return ordered_moves


# =========================================================================
# SECTION 6: Killer moves and history heuristic
# =========================================================================

def add_killer_move(depth, move):
    """Record a beta-cutoff move at `depth` as a killer.

    Killer moves are stored per depth (2 per depth). If the same position
    appears in a different branch at the same depth, the killer move is
    searched early, often causing a beta cutoff again.
    """
    if move in killer_moves[depth]:
        return
    killer_moves[depth].insert(0, move)
    if len(killer_moves[depth]) > 2:
        killer_moves[depth].pop()


def add_history_score(depth, row, col):
    """Increment the history score for this cell.

    History heuristic tracks which cells have repeatedly caused beta cutoffs.
    Cells with high history scores are searched earlier in sibling nodes.
    Score increment is proportional to depth squared so deeper cutoffs count more.
    """
    history_score[row][col] += depth * depth


# =========================================================================
# SECTION 7: Minimax search with quiescence
# =========================================================================

def minimax(board, depth, maximizing, alpha, beta):
    """Convenience wrapper: compute zobrist hash and eval, then call _minimax."""
    zhash = compute_zobrist(board)
    score = evaluate_board(board)
    return _minimax(board, depth, maximizing, alpha, beta, zhash, score, None)


def _quiescence_search(board, player, alpha, beta, zhash, score, last_move, depth):
    """Quiescence search — extend search at leaf nodes when threats are present.

    The horizon effect: tactical sequences (captures, forks) that are just
    below the search depth are invisible to the evaluation. Quiescence search
    resolves this by only searching "noisy" moves (moves that create or block
    fours and open-threes) until a quiet position is reached.

    Uses stand-pat: if the current evaluation already exceeds beta, return
    immediately (no need to search further — the opponent won't allow this).
    """
    if depth <= 0:
        return score

    # Stand-pat cutoff
    if score >= beta:
        return score

    cand = get_candidate_moves(board, distance=1)
    # Only search threatening moves (fours and open-threes)
    for row, col in cand:
        if not _is_threatening_move(board, row, col, AI) and not _is_threatening_move(board, row, col, PLAYER):
            continue
        delta = compute_move_delta(board, row, col, player)
        board[row][col] = player
        new_zhash = update_zobrist(zhash, row, col, EMPTY, player) if zhash is not None else None
        if check_winner_fast(board, player, (row, col)):
            board[row][col] = EMPTY
            return WIN_SCORE + depth if player == AI else -(WIN_SCORE + depth)
        value = _quiescence_search(board, AI if player == PLAYER else PLAYER,
                                   alpha, beta, new_zhash, score + delta, (row, col), depth - 1)
        board[row][col] = EMPTY
        if player == AI:
            if value > alpha:
                alpha = value
            if alpha >= beta:
                break
        else:
            if value < beta:
                beta = value
            if alpha >= beta:
                break
    return alpha if player == AI else beta


def _is_threatening_move(board, row, col, player):
    """Check if placing `player` at (row, col) creates a threat worth extending for.

    Used by quiescence search to filter non-threatening moves.
    Only extends for fours (any kind) and open-threes.
    """
    board[row][col] = player
    for dr1, dc1, dr2, dc2 in AXES:
        cat, total = classify_axis(board, row, col, player, dr1, dc1, dr2, dc2)
        if cat in (THREAT_OPEN_FOUR, THREAT_SEMI_OPEN_FOUR, THREAT_OPEN_THREE, THREAT_FIVE):
            board[row][col] = EMPTY
            return True
    board[row][col] = EMPTY
    return False


def _limit_candidates(moves, depth):
    """Cap the number of candidate moves based on search depth.

    Fewer candidates at deeper depths to control search explosion:
    depth 1-2: up to 24 candidates
    depth 3-4: up to 18 candidates
    depth 5+:  up to 14 candidates

    Since moves are already ordered by priority, the tail of the list
    is the least promising moves and can be safely pruned.
    """
    if depth <= CANDIDATE_LIMIT_DEPTH_EARLY:
        return moves[:CANDIDATE_LIMIT_EARLY]
    if depth <= CANDIDATE_LIMIT_DEPTH_MID:
        return moves[:CANDIDATE_LIMIT_MID]
    return moves[:CANDIDATE_LIMIT_DEEP]


def _minimax(board, depth, maximizing, alpha, beta, zhash, score, last_move):
    """Alpha-beta minimax with transposition table, LMR, and heuristics.

    This is the core recursive search function. For the maximizing side (AI),
    it searches for the highest score; for the minimizing side (PLAYER), the lowest.

    Optimizations applied:
    1. Transposition table probe — skip if already evaluated deeper
    2. Move ordering — search best moves first for better pruning
    3. Candidate limiting — cap branching factor at deep depths
    4. Late Move Reduction — reduce search depth for late moves
    5. Killer/history update — record beta-cutoff moves for move ordering
    6. TT store — save result for future probes
    """
    # Fast terminal check using last_move (O(depth) instead of O(n²))
    if last_move is not None:
        if check_winner_fast(board, AI, last_move):
            return WIN_SCORE
        if check_winner_fast(board, PLAYER, last_move):
            return -WIN_SCORE
    else:
        if check_winner(board, AI):
            return WIN_SCORE
        if check_winner(board, PLAYER):
            return -WIN_SCORE

    if is_board_full(board):
        return 0

    if depth <= 0:
        return score

    # TT probe — if found, skip search entirely
    if zhash is not None:
        tt_found, tt_score, tt_best = tt_probe(zhash, depth, alpha, beta)
        if tt_found:
            return tt_score
    else:
        tt_best = None

    candidate_moves = get_candidate_moves(board, distance=1)
    if not candidate_moves:
        return score

    if maximizing:
        candidate_moves = order_moves(board, candidate_moves, AI, depth, tt_best)
        candidate_moves = _limit_candidates(candidate_moves, depth)
        best_value = float("-inf")
        best_move = None
        orig_alpha = alpha

        for mi, (row, col) in enumerate(candidate_moves):
            delta = compute_move_delta(board, row, col, AI)
            board[row][col] = AI
            new_zhash = update_zobrist(zhash, row, col, EMPTY, AI) if zhash is not None else None

            # Late Move Reduction: reduce depth for late moves in the ordering
            if depth >= LMR_DEPTH_THRESHOLD and mi >= LMR_MOVES_THRESHOLD:
                reduced = _minimax(board, depth - 1 - LMR_REDUCTION, False,
                                   alpha, beta, new_zhash, score + delta, (row, col))
                # Re-search at full depth if the reduced search was promising
                if reduced > alpha:
                    value = _minimax(board, depth - 1, False, alpha, beta,
                                     new_zhash, score + delta, (row, col))
                else:
                    value = reduced
            else:
                value = _minimax(board, depth - 1, False, alpha, beta,
                                 new_zhash, score + delta, (row, col))
            board[row][col] = EMPTY

            if value > best_value:
                best_value = value
                best_move = (row, col)

            if best_value > alpha:
                alpha = best_value

            if alpha >= beta:
                add_killer_move(depth, (row, col))
                add_history_score(depth, row, col)
                break

        if zhash is not None:
            flag = EXACT
            if best_value <= orig_alpha:
                flag = UPPERBOUND
            elif best_value >= beta:
                flag = LOWERBOUND
            tt_store(zhash, depth, best_value, flag, best_move)

        return best_value

    else:
        candidate_moves = order_moves(board, candidate_moves, PLAYER, depth, tt_best)
        candidate_moves = _limit_candidates(candidate_moves, depth)
        best_value = float("inf")
        best_move = None
        orig_alpha = alpha

        for mi, (row, col) in enumerate(candidate_moves):
            delta = compute_move_delta(board, row, col, PLAYER)
            board[row][col] = PLAYER
            new_zhash = update_zobrist(zhash, row, col, EMPTY, PLAYER) if zhash is not None else None

            # Late Move Reduction
            if depth >= LMR_DEPTH_THRESHOLD and mi >= LMR_MOVES_THRESHOLD:
                reduced = _minimax(board, depth - 1 - LMR_REDUCTION, True,
                                   alpha, beta, new_zhash, score + delta, (row, col))
                if reduced < beta:
                    value = _minimax(board, depth - 1, True, alpha, beta,
                                     new_zhash, score + delta, (row, col))
                else:
                    value = reduced
            else:
                value = _minimax(board, depth - 1, True, alpha, beta,
                                 new_zhash, score + delta, (row, col))
            board[row][col] = EMPTY

            if value < best_value:
                best_value = value
                best_move = (row, col)

            if best_value < beta:
                beta = best_value

            if alpha >= beta:
                add_killer_move(depth, (row, col))
                add_history_score(depth, row, col)
                break

        if zhash is not None:
            flag = EXACT
            if best_value <= orig_alpha:
                flag = UPPERBOUND
            elif best_value >= beta:
                flag = LOWERBOUND
            tt_store(zhash, depth, best_value, flag, best_move)

        return best_value


# =========================================================================
# SECTION 8: Pre-search priority pipeline
# =========================================================================

def find_best_move_by_minimax(board, depth):
    """Find the best move for the AI using pre-search pipeline + minimax.

    The pre-search pipeline evaluates ALL candidate moves and assigns
    attack/defense priorities. This is critical because shallow-depth
    minimax suffers from the horizon effect: a winning tactic may be
    one ply beyond the search depth.

    Pipeline stages (checked in order, returns at first match):
    ------------------------------------------------------------------
    1. AI immediate win (5 in a row)        Priority 1 → instant win
    2. Opponent immediate win               Priority 2 → must block

    Then scan ALL candidates for threat/defense priorities.
    Lower number = more urgent.

    Attack priorities:
        10 → AI creates five
        20 → AI double-four fork
        22 → AI four-three fork
        24 → AI open-four
        29 → AI double-three fork
        34 → AI semi-open-four
        36 → AI open-three

    Defense priorities:
         5 → Opponent would win if AI plays here
         9 → Opponent open-four (must block)
        15 → Opponent double-four fork
        18 → Opponent four-three fork
        23 → Opponent double-three fork
        26 → Opponent semi-open-four
        35 → Opponent open-three

    Decision: attack if attack_priority < defense_priority,
    defense if defense_priority < attack_priority.
    If equal (or no threats found), fall through to search.
    ------------------------------------------------------------------
    """
    candidate_moves = get_candidate_moves(board, distance=1)

    if not candidate_moves:
        return None

    # Priority 1: AI immediate win = play the winning move
    ai_wins = find_immediate_winning_moves(board, AI)
    if ai_wins:
        return random.choice(ai_wins)

    # Priority 2: Opponent is about to win = block
    player_wins = find_immediate_winning_moves(board, PLAYER)
    if player_wins:
        return random.choice(player_wins)

    # Priorities 3-10: Scan ALL candidates for threats and forks
    best_attack_move = None
    best_attack_priority = 999       # 999 = no threat found
    best_defense_move = None
    best_defense_priority = 999

    for row, col in candidate_moves:
        # --- Evaluate attack: what does AI get by playing here? ---
        board[row][col] = AI
        ai_fork = detect_fork(board, row, col, AI)
        ai_is_win = check_winner_fast(board, AI, (row, col))
        ai_threat, _ = find_single_axis_threat(board, row, col, AI)
        board[row][col] = EMPTY

        # --- Evaluate defense: what does opponent get if AI plays here? ---
        board[row][col] = PLAYER
        opp_fork = detect_fork(board, row, col, PLAYER)
        opp_is_win = check_winner_fast(board, PLAYER, (row, col))
        opp_threat, _ = find_single_axis_threat(board, row, col, PLAYER)
        board[row][col] = EMPTY

        ai_priority = 999
        opp_priority = 999

        # Attack priority ladder (lower = more urgent, 20 < 24 means more urgent)
        if ai_is_win:
            ai_priority = 10
        elif ai_fork == FORK_DOUBLE_FOUR:
            ai_priority = 20
        elif ai_fork == FORK_FOUR_THREE:
            ai_priority = 22          # stronger than open-four: forced win
        elif ai_threat == THREAT_OPEN_FOUR:
            ai_priority = 24          # strong but opponent can block on 1 axis
        elif ai_fork == FORK_DOUBLE_THREE:
            ai_priority = 29
        elif ai_threat == THREAT_SEMI_OPEN_FOUR:
            ai_priority = 34
        elif ai_threat == THREAT_OPEN_THREE:
            ai_priority = 36

        # Defense priority ladder (lower = more urgent)
        if opp_is_win:
            opp_priority = 5           # absolute must-block — losing otherwise
        elif opp_threat == THREAT_OPEN_FOUR:
            opp_priority = 9           # must block — opponent can win next move
        elif opp_fork == FORK_DOUBLE_FOUR:
            opp_priority = 15
        elif opp_fork == FORK_FOUR_THREE:
            opp_priority = 18
        elif opp_threat == THREAT_SEMI_OPEN_FOUR:
            opp_priority = 26
        elif opp_fork == FORK_DOUBLE_THREE:
            opp_priority = 23          # more urgent than creating open-four (24)
        elif opp_threat == THREAT_OPEN_THREE:
            opp_priority = 35

        # Track best of each category
        if ai_priority < best_attack_priority:
            best_attack_priority = ai_priority
            best_attack_move = (row, col)

        if opp_priority < best_defense_priority:
            best_defense_priority = opp_priority
            best_defense_move = (row, col)

    # Compare attack vs defense:
    # Attack only if strictly more urgent (lower priority number).
    # If defense is equally urgent, defense wins (prevents the opponent from equalizing).
    if best_attack_priority < best_defense_priority:
        return best_attack_move
    if best_defense_priority < best_attack_priority:
        return best_defense_move

    # No decisive threat found — fall through to iterative deepening search
    return _iterative_deepening_search(board, depth)


# =========================================================================
# SECTION 9: Iterative Deepening Search
# =========================================================================

def _iterative_deepening_search(board, depth):
    """Core iterative deepening search with aspiration windows.

    This can be used as a standalone entry point (without pre-search pipeline)
    when threat_detection is disabled in the simulation. It matches the
    (board, depth) signature of find_best_move_by_minimax for seamless
    monkey-patching.

    Iterative deepening: searches at depth 1, then 2, ..., up to `depth`.
    Benefits:
    - Move ordering from shallower searches improves pruning at deeper searches
    - Aspiration windows narrow alpha-beta bounds based on previous score
    - Always has a best move available if time runs out

    Aspiration window: after depth 1, the search window is narrowed to
    [prev_score - WINDOW, prev_score + WINDOW]. If the score falls outside
    this range (estimate was wrong), re-search with full width.
    """
    from board import get_candidate_moves
    from evaluation import evaluate_board
    from zobrist import compute_zobrist

    candidate_moves = get_candidate_moves(board, 1)
    if not candidate_moves:
        return None

    tt_new_search()
    killer_moves.update({d: [] for d in range(MAX_DEPTH + 1)})
    zhash = compute_zobrist(board)
    score = evaluate_board(board)

    prev_score = None
    best_move = candidate_moves[0]

    for search_depth in range(1, depth + 1):
        alpha = float("-inf")
        beta = float("inf")

        # Narrow window using previous depth's score
        if prev_score is not None:
            alpha = prev_score - ASPIRATION_WINDOW
            beta = prev_score + ASPIRATION_WINDOW

        value, move = search_root_id(board, search_depth, alpha, beta, zhash, score)

        # Aspiration fail — re-search with full window
        if value <= alpha or value >= beta:
            value, move = search_root_id(board, search_depth, float("-inf"), float("inf"), zhash, score)

        if move is not None:
            best_move = move
        prev_score = value

    return best_move


# =========================================================================
# SECTION 10: Root-level search (one depth)
# =========================================================================

def search_root_id(board, depth, alpha, beta, zhash, score):
    """Search the root position at a specific depth.

    This is called by _iterative_deepening_search() for each depth level.
    It orders root moves using the previous iteration's TT best-move hints,
    applies LMR at the root, and stores the result in the TT.

    Returns (score, best_move) tuple — the score for this depth and the
    best move found. The score feeds the aspiration window for the next depth.
    """
    candidate_moves = get_candidate_moves(board, distance=1)
    if not candidate_moves:
        return score, None

    candidate_moves = order_moves(board, candidate_moves, AI, depth)
    candidate_moves = _limit_candidates(candidate_moves, depth)

    best_value = float("-inf")
    best_move = candidate_moves[0]
    orig_alpha = alpha

    for mi, (row, col) in enumerate(candidate_moves):
        delta = compute_move_delta(board, row, col, AI)
        board[row][col] = AI
        new_zhash = update_zobrist(zhash, row, col, EMPTY, AI) if zhash is not None else None

        if depth >= LMR_DEPTH_THRESHOLD and mi >= LMR_MOVES_THRESHOLD:
            reduced = _minimax(board, depth - 1 - LMR_REDUCTION, False,
                               alpha, beta, new_zhash, score + delta, (row, col))
            if reduced > alpha:
                value = _minimax(board, depth - 1, False, alpha, beta,
                                 new_zhash, score + delta, (row, col))
            else:
                value = reduced
        else:
            value = _minimax(board, depth - 1, False, alpha, beta,
                             new_zhash, score + delta, (row, col))
        board[row][col] = EMPTY

        if value > best_value:
            best_value = value
            best_move = (row, col)

        if best_value > alpha:
            alpha = best_value

        if alpha >= beta:
            break

    if zhash is not None:
        flag = EXACT
        if best_value <= orig_alpha:
            flag = UPPERBOUND
        elif best_value >= beta:
            flag = LOWERBOUND
        tt_store(zhash, depth, best_value, flag, best_move)

    return best_value, best_move


# =========================================================================
# SECTION 11: Public entry point
# =========================================================================

def ai_move(board, level):
    """Public entry point — called by the game UI and console.

    Maps difficulty levels to search depth:
    - EASY   (1) → depth 1 (shallow, weak)
    - MEDIUM (2) → depth 2
    - HARD   (3) → depth MAX_DEPTH=5 (with iterative deepening)
    """
    if level == EASY:
        return find_best_move_by_minimax(board, depth=1)
    elif level == MEDIUM:
        return find_best_move_by_minimax(board, depth=2)
    return find_best_move_by_minimax(board, depth=MAX_DEPTH)
