import random
import time

from constants import EMPTY, PLAYER, AI, WIN_SCORE, EASY, MEDIUM, HARD, MAX_DEPTH
from board import get_candidate_moves
from rules import check_winner, is_board_full
from evaluation import evaluate_board

# Killer moves nên được quản lý hoặc reset theo từng lượt search lớn
killer_moves = {}
IDS_TIME_LIMITS = {
    EASY: 0.2,
    MEDIUM: 2,
    HARD: 6,
}


class SearchTimeout(Exception):
    pass


def is_time_up(deadline):
    return deadline is not None and time.perf_counter() >= deadline


def find_immediate_winning_moves(board, player):
    winning_moves = []
    candidate_moves = get_candidate_moves(board, distance=1)

    for row, col in candidate_moves:
        board[row][col] = player
        if check_winner(board, player):
            winning_moves.append((row, col))
        board[row][col] = EMPTY

    return winning_moves


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


def order_moves(board, candidate_moves, player, depth, previous_best_move=None):
    scored_moves = []

    for row, col in candidate_moves:
        move = (row, col)
        # Nếu là nước đi tốt nhất từ độ sâu trước, cho điểm  cao để xét đầu tiên
        if previous_best_move == move:
            score = 10**10
        else:
            score = evaluate_for_ordering_move(board, row, col, player, depth)
        
        scored_moves.append((move, score))


    scored_moves.sort(key=lambda x: x[1], reverse=True)

    return [move for move, score in scored_moves]


def add_killer_move(depth, move):
    if depth not in killer_moves:
        killer_moves[depth] = []
    if move in killer_moves[depth]:
        return
    
    killer_moves[depth].insert(0, move)
    if len(killer_moves[depth]) > 2:
        killer_moves[depth].pop()


def minimax(board, depth, maximizing, alpha, beta, deadline=None):
    if is_time_up(deadline):
        raise SearchTimeout

    # 1. Kiểm tra trạng thái kết thúc
    if check_winner(board, AI):
        return WIN_SCORE
    if check_winner(board, PLAYER):
        return -WIN_SCORE
    if is_board_full(board):
        return 0
    
    # 2. Nếu đạt độ sâu giới hạn
    if depth <= 0:
        return evaluate_board(board)
    
    candidate_moves = get_candidate_moves(board, distance=1)
    if not candidate_moves:
        return evaluate_board(board)
    
    # 3. Lượt AI (Maximizing)
    if maximizing:
        candidate_moves = order_moves(board, candidate_moves, AI, depth)
        best_value = float("-inf")

        for row, col in candidate_moves:
            if is_time_up(deadline):
                raise SearchTimeout

            board[row][col] = AI
            try:
                value = minimax(board, depth - 1, False, alpha, beta, deadline)
            finally:
                board[row][col] = EMPTY

            if value > best_value:
                best_value = value
            if best_value > alpha:
                alpha = best_value

            if alpha >= beta:
                add_killer_move(depth, (row, col))
                break

        return best_value
    
    # 4. Lượt Người chơi (Minimizing)
    else:
        candidate_moves = order_moves(board, candidate_moves, PLAYER, depth)
        best_value = float("inf")

        for row, col in candidate_moves:
            if is_time_up(deadline):
                raise SearchTimeout

            board[row][col] = PLAYER
            try:
                value = minimax(board, depth - 1, True, alpha, beta, deadline)
            finally:
                board[row][col] = EMPTY

            if value < best_value:
                best_value = value
            if best_value < beta:
                beta = best_value

            if alpha >= beta:
                add_killer_move(depth, (row, col))
                break

        return best_value


def find_best_move_by_minimax(board, depth, deadline=None, check_immediate=True, previous_best_move=None):
    candidate_moves = get_candidate_moves(board, distance=1)
    if not candidate_moves:
        return None
    
    if check_immediate:
        ai_wins = find_immediate_winning_moves(board, AI)
        if ai_wins:
            return random.choice(ai_wins)

        player_wins = find_immediate_winning_moves(board, PLAYER)
        if player_wins:
            return random.choice(player_wins)

    # Truyền thêm previous_best_move vào để tối ưu cắt tỉa góc Alpha-Beta tốt hơn nữa
    candidate_moves = order_moves(board, candidate_moves, AI, depth, previous_best_move)

    best_score = float("-inf")
    best_moves = []

    for row, col in candidate_moves:
        if is_time_up(deadline):
            raise SearchTimeout

        board[row][col] = AI
        try:
            score = minimax(board, depth - 1, False, float("-inf"), float("inf"), deadline)
        finally:
            board[row][col] = EMPTY

        if score > best_score:
            best_score = score
            best_moves = [(row, col)]
        elif score == best_score:
            best_moves.append((row, col))

    if best_moves:
        return random.choice(best_moves)
    return None


def find_best_move_by_ids(board, max_depth, time_limit):
    global killer_moves
    killer_moves = {} # Reset killer moves cho lượt đi mới sạch sẽ

    candidate_moves = get_candidate_moves(board, distance=1)
    if not candidate_moves:
        return None

    ai_wins = find_immediate_winning_moves(board, AI)
    if ai_wins:
        return random.choice(ai_wins)

    player_wins = find_immediate_winning_moves(board, PLAYER)
    if player_wins:
        return random.choice(player_wins)

    deadline = time.perf_counter() + time_limit
    best_move = None
    best_depth = 0

    for depth in range(1, max_depth + 1):
        try:
            # Truyền best_move của độ sâu trước vào để tối ưu hóa việc duyệt ở độ sâu sau
            move = find_best_move_by_minimax(
                board,
                depth,
                deadline=deadline,
                check_immediate=False,
                previous_best_move=best_move
            )
        except SearchTimeout:
            break

        if move is not None:
            best_move = move
            best_depth = depth

    if best_move is not None:
        print(f"AI chose {best_move} from completed depth {best_depth}")
        return best_move

    fallback_move = random.choice(order_moves(board, candidate_moves, AI, 1))
    print(f"AI chose {fallback_move} from fallback ordering")
    return fallback_move


def ai_move(board, level):
    if level == EASY:
        return find_best_move_by_ids(board, max_depth=1, time_limit=IDS_TIME_LIMITS[EASY])
    elif level == MEDIUM:
        return find_best_move_by_ids(board, max_depth=2, time_limit=IDS_TIME_LIMITS[MEDIUM])
    # HARD
    return find_best_move_by_ids(board, max_depth=4, time_limit=IDS_TIME_LIMITS[HARD])
