import random

from constants import EMPTY, PLAYER, AI, WIN_SCORE, EASY, MEDIUM, HARD
from board import get_candidate_moves
from rules import check_winner
from evaluation import evaluate_board
from rules import is_board_full


def find_immediate_winning_moves(board, player):
    winning_moves = []
    candidate_moves = get_candidate_moves(board, distance=1)

    for row, col in candidate_moves:
        board[row][col] = player

        if check_winner(board, player):
            winning_moves.append((row, col))

        board[row][col] = EMPTY

    return winning_moves



def ai_random_move(board):
    candidate_moves= get_candidate_moves(board, distance=1)
    if not candidate_moves:
        return None

    return random.choice(candidate_moves)


# def find_best_move_by_heuristic(board):
#     candidate_moves = get_candidate_moves(board, distance=1)

#     if not candidate_moves:
#         return None

#     # 1. AI có nước thắng ngay
#     ai_wins = find_immediate_winning_moves(board, AI)
#     if ai_wins:
#         return random.choice(ai_wins)

#     # 2. Người chơi có nước thắng ngay thì chặn
#     player_wins = find_immediate_winning_moves(board, PLAYER)
#     if player_wins:
#         return random.choice(player_wins)

#     # 3. Dùng heuristic
#     best_score = float("-inf")
#     best_moves = []

#     for row, col in candidate_moves:
#         board[row][col] = AI
#         score = evaluate_board(board)
#         board[row][col] = EMPTY

#         if score > best_score:
#             best_score = score
#             best_moves = [(row, col)]
#         elif score == best_score:
#             best_moves.append((row, col))

#     return random.choice(best_moves)



def minimax(board, depth, maximizing, alpha, beta):
    #1. Kiểm tra trạng thái kết thúc
    if check_winner(board, AI):
        return WIN_SCORE
    
    if check_winner(board, PLAYER):
        return -WIN_SCORE
    
    if is_board_full(board):
        return 0
    
    #2. Nếu đạt độ sâu giới hạn, dùng heuristic
    if depth == 0:
        return evaluate_board(board)
    
    candidate_moves = get_candidate_moves(board, distance=1)

    if not candidate_moves:
        return evaluate_board(board)
    
    #3. Nếu là lượt AI
    if maximizing:
        best_value = float("-inf")

        for row, col in candidate_moves:
            board[row][col] = AI
            value = minimax(board, depth - 1, False, alpha, beta)
            board[row][col] = EMPTY

            if value > best_value:
                best_value = value
                
            if best_value > alpha:
                alpha = best_value

            # Alpha-Beta pruning
            if alpha >= beta:
                break

        return best_value
    
    #4. Nếu là người chơi
    else:
        best_value = float("inf")

        for row, col in candidate_moves:
            board[row][col] = PLAYER
            value = minimax(board, depth - 1, True, alpha, beta)
            board[row][col] = EMPTY

            if value < best_value:
                best_value = value

            if best_value < beta:
                beta = best_value

            #Alpha-beta pruning
            if alpha >= beta:
                break

        return best_value



def find_best_move_by_minimax(board, depth):
    candidate_moves = get_candidate_moves(board, distance=1)

    if not candidate_moves:
        return None
    
     # Ưu tiên xử lý tình huống khẩn cấp
    ai_wins = find_immediate_winning_moves(board, AI)
    if ai_wins:
        return random.choice(ai_wins)

    
    player_wins = find_immediate_winning_moves(board, PLAYER)
    if player_wins:
        return random.choice(player_wins)

    best_score = float("-inf")
    best_moves = []

    for row, col in candidate_moves:
        board[row][col] = AI
        score = minimax(board, depth - 1, False, float("-inf"), float("inf"))
        board[row][col] = EMPTY

        if score > best_score:
            best_score = score
            best_moves = [(row, col)]
        elif score == best_score:
            best_moves.append((row, col))

    if best_moves:
        return random.choice(best_moves)
    
    return None


def ai_move(board, level):
    if level == EASY:
        return ai_random_move(board)
    elif level == MEDIUM:
        return find_best_move_by_minimax(board, depth=1)
    #HARD
    return find_best_move_by_minimax(board, depth=3)




