import random

from constants import EMPTY, PLAYER, AI, WIN_SCORE, EASY, MEDIUM, HARD, MAX_DEPTH
from board import get_candidate_moves
from rules import check_winner, is_board_full
from evaluation import evaluate_board

killer_moves = {d: [] for d in range(MAX_DEPTH + 1)}


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



def evaluate_for_ordering_move(board, row, col, player, depth):
    move = (row, col)
    killer_bonus = 10**8 if move in killer_moves.get(depth, []) else 0

    board[row][col] = player
    if check_winner(board, player):
        board[row][col] = EMPTY
        return 10**9 + killer_bonus
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
    return killer_bonus + ally_neighbors * 10 + opponent_neighbors * 6 + center_bonus


def order_moves(board, candidate_moves, player, depth):
    scored_moves = []

    for row, col in candidate_moves:
        score = evaluate_for_ordering_move(board, row, col, player, depth)

        #ưu tiên killer_move
        scored_moves.append(((row, col), score))

    #AI muốn điểm cao trước
    if player == AI:
        scored_moves.sort(key=lambda x: x[1], reverse=True)
    else:
        #Người chơi muốn điểm thấp trước
        scored_moves.sort(key=lambda x: x[1], reverse=True)

    ordered_moves = [move for move, score in scored_moves]
    return ordered_moves

def add_killer_move(depth, move):
    if move in killer_moves[depth]:
        return
    
    killer_moves[depth].insert(0, move)

    #Giữ tối đa 2 killer moves cho mỗi depth
    if len(killer_moves[depth]) > 2:
        killer_moves[depth].pop()





def minimax(board, depth, maximizing, alpha, beta):
    #1. Kiểm tra trạng thái kết thúc
    if check_winner(board, AI):
        return WIN_SCORE
    
    if check_winner(board, PLAYER):
        return -WIN_SCORE
    
    if is_board_full(board):
        return 0
    
    #2. Nếu đạt độ sâu giới hạn, dùng heuristic
    if depth <= 0:
        return evaluate_board(board)
    
    candidate_moves = get_candidate_moves(board, distance=1)

    if not candidate_moves:
        return evaluate_board(board)
    
    #3. Nếu là lượt AI
    if maximizing:
        candidate_moves = order_moves(board, candidate_moves, AI, depth)
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
                add_killer_move(depth, (row, col))
                break

        return best_value
    
    #4. Nếu là người chơi
    else:
        candidate_moves = order_moves(board, candidate_moves, PLAYER, depth)
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
                add_killer_move(depth, (row, col))
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

    candidate_moves = order_moves(board, candidate_moves, AI, depth)

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



