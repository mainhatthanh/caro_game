import random

from constants import EMPTY, PLAYER, AI
from board import get_candidate_moves
from rules import check_winner
from evaluation import evaluate_board


def find_immediate_winning_moves(board, player):
    winning_moves = []
    candidate_moves = get_candidate_moves(board, distance=1)

    for row, col in candidate_moves:
        board[row][col] = player

        if check_winner(board, player):
            winning_moves.append((row, col))

        board[row][col] = EMPTY

    return winning_moves


def find_best_move_by_heuristic(board):
    candidate_moves = get_candidate_moves(board, distance=1)

    if not candidate_moves:
        return None

    # 1. AI có nước thắng ngay
    ai_wins = find_immediate_winning_moves(board, AI)
    if ai_wins:
        return random.choice(ai_wins)

    # 2. Người chơi có nước thắng ngay thì chặn
    player_wins = find_immediate_winning_moves(board, PLAYER)
    if player_wins:
        return random.choice(player_wins)

    # 3. Dùng heuristic
    best_score = float("-inf")
    best_moves = []

    for row, col in candidate_moves:
        board[row][col] = AI
        score = evaluate_board(board)
        board[row][col] = EMPTY

        if score > best_score:
            best_score = score
            best_moves = [(row, col)]
        elif score == best_score:
            best_moves.append((row, col))

    return random.choice(best_moves)


def ai_move(board):
    return find_best_move_by_heuristic(board)


# def ai_random_move(board):
#     candidate_moves= get_candidate_moves(board, distance=1)
#     if not candidate_moves:
#         return None

#     return random.choice(candidate_moves)