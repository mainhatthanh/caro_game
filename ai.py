import random

from constants import EMPTY, PLAYER, AI, WIN_SCORE, EASY, MEDIUM, MAX_DEPTH, BOARD_SIZE
from board import get_candidate_moves
from rules import check_winner, is_board_full, check_winner_fast
from evaluation import evaluate_board, compute_move_delta
from zobrist import (
    tt_probe, tt_store, compute_zobrist, update_zobrist,
    EXACT, LOWERBOUND, UPPERBOUND,
)

killer_moves = {d: [] for d in range(MAX_DEPTH + 1)}
history_score = [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)]


def add_history_score(depth, row, col):
    history_score[row][col] += depth * depth


def find_immediate_winning_moves(board, player):
    winning_moves = []
    candidate_moves = get_candidate_moves(board, distance=1)

    for row, col in candidate_moves:
        board[row][col] = player
        if check_winner_fast(board, player, (row, col)):
            winning_moves.append((row, col))
        board[row][col] = EMPTY

    return winning_moves


def evaluate_for_ordering_move(board, row, col, player, depth):
    move = (row, col)
    killer_bonus = 10**8 if move in killer_moves.get(depth, []) else 0

    board[row][col] = player
    if check_winner_fast(board, player, (row, col)):
        board[row][col] = EMPTY
        return 10**9 + killer_bonus + history_score[row][col]
    board[row][col] = EMPTY

    ally_neighbors = 0
    opponent_neighbors = 0
    center = len(board) // 2

    for dr in range(-1, 2):
        for dc in range(-1, 2):
            if dr == 0 and dc == 0:
                continue
            nr = row + dr
            nc = col + dc
            if 0 <= nr < len(board) and 0 <= nc < len(board):
                if board[nr][nc] == player:
                    ally_neighbors += 1
                elif board[nr][nc] != EMPTY:
                    opponent_neighbors += 1

    center_bonus = max(0, center - abs(row - center) - abs(col - center))
    return killer_bonus + ally_neighbors * 10 + opponent_neighbors * 6 + center_bonus + history_score[row][col]


def order_moves(board, candidate_moves, player, depth, hash_move=None):
    scored_moves = []

    for row, col in candidate_moves:
        s = evaluate_for_ordering_move(board, row, col, player, depth)
        if hash_move and (row, col) == hash_move:
            s += 10**9
        scored_moves.append(((row, col), s))

    scored_moves.sort(key=lambda x: x[1], reverse=True)
    ordered_moves = [move for move, score in scored_moves]
    return ordered_moves


def add_killer_move(depth, move):
    if move in killer_moves[depth]:
        return
    killer_moves[depth].insert(0, move)
    if len(killer_moves[depth]) > 2:
        killer_moves[depth].pop()


def minimax(board, depth, maximizing, alpha, beta):
    zhash = compute_zobrist(board)
    score = evaluate_board(board)
    return _minimax(board, depth, maximizing, alpha, beta, zhash, score, None)


def _minimax(board, depth, maximizing, alpha, beta, zhash, score, last_move):
    # Fast terminal check
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

    # TT probe
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
        best_value = float("-inf")
        best_move = None
        orig_alpha = alpha

        for row, col in candidate_moves:
            delta = compute_move_delta(board, row, col, AI)
            board[row][col] = AI
            new_zhash = update_zobrist(zhash, row, col, EMPTY, AI) if zhash is not None else None
            value = _minimax(board, depth - 1, False, alpha, beta, new_zhash, score + delta, (row, col))
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
        best_value = float("inf")
        best_move = None
        orig_alpha = alpha

        for row, col in candidate_moves:
            delta = compute_move_delta(board, row, col, PLAYER)
            board[row][col] = PLAYER
            new_zhash = update_zobrist(zhash, row, col, EMPTY, PLAYER) if zhash is not None else None
            value = _minimax(board, depth - 1, True, alpha, beta, new_zhash, score + delta, (row, col))
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


def find_best_move_by_minimax(board, depth):
    candidate_moves = get_candidate_moves(board, distance=1)

    if not candidate_moves:
        return None

    # Immediate win/block
    ai_wins = find_immediate_winning_moves(board, AI)
    if ai_wins:
        return random.choice(ai_wins)

    player_wins = find_immediate_winning_moves(board, PLAYER)
    if player_wins:
        return random.choice(player_wins)

    zhash = compute_zobrist(board)
    score = evaluate_board(board)
    candidate_moves = order_moves(board, candidate_moves, AI, depth, None)

    best_score = float("-inf")
    best_moves = []

    for row, col in candidate_moves:
        delta = compute_move_delta(board, row, col, AI)
        board[row][col] = AI
        new_zhash = update_zobrist(zhash, row, col, EMPTY, AI)
        value = _minimax(board, depth - 1, False, float("-inf"), float("inf"), new_zhash, score + delta, (row, col))
        board[row][col] = EMPTY

        if value > best_score:
            best_score = value
            best_moves = [(row, col)]
        elif value == best_score:
            best_moves.append((row, col))

    if best_moves:
        return random.choice(best_moves)

    return None


def ai_move(board, level):
    if level == EASY:
        return find_best_move_by_minimax(board, depth=1)
    elif level == MEDIUM:
        return find_best_move_by_minimax(board, depth=2)
    return find_best_move_by_minimax(board, depth=3)
