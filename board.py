from constants import BOARD_SIZE, EMPTY, PLAYER, AI


def create_board():
    return [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]


def print_board(board):
    print("  ", end="")
    for col in range(BOARD_SIZE):
        print(f"{col}", end="")
    print()

    for row in range(BOARD_SIZE):
        print(f"{row:2}", end="")
        for col in range(BOARD_SIZE):
            if board[row][col] == PLAYER:
                symbol = "X"
            elif board[row][col] == AI:
                symbol = "O"
            else:
                symbol = "."
            print(symbol, end="")
        print()


def make_move(board, row, col, player):
    if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
        if board[row][col] == EMPTY:
            board[row][col] = player
            return True
    return False


def get_player_move():
    while True:
        try:
            row = int(input("Nhap hang (0 - 14): "))
            col = int(input("Nhap cot (0 - 14): "))
            return row, col
        except ValueError:
            print("Vui long nhap so nguyen")


def get_empty_cells(board):
    empty_cells = []

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY:
                empty_cells.append((row, col))

    return empty_cells


def has_neighbor(board, row, col, distance=1):
    for dr in range(-distance, distance + 1):
        for dc in range(-distance, distance + 1):
            if dr == 0 and dc == 0:
                continue

            nr = row + dr
            nc = col + dc

            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE:
                if board[nr][nc] != EMPTY:
                    return True

    return False


def get_candidate_moves(board, distance=1):
    candidate_moves = []

    is_empty_board = True
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] != EMPTY:
                is_empty_board = False
                break
        if not is_empty_board:
            break

    if is_empty_board:
        center = BOARD_SIZE // 2
        return [(center, center)]

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY and has_neighbor(board, row, col, distance):
                candidate_moves.append((row, col))

    return candidate_moves