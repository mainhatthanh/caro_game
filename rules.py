from constants import BOARD_SIZE, EMPTY, PLAYER, AI


def check_five_from_cell(board, row, col, player):
    directions = [
        (0, 1),   # ngang
        (1, 0),   # dọc
        (1, 1),   # chéo xuống phải
        (1, -1),  # chéo xuống trái
    ]

    opponent = PLAYER if player == AI else AI

    for dr, dc in directions:
        cells = []

        for i in range(5):
            r = row + dr * i
            c = col + dc * i

            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
                cells.append((r, c))
            else:
                break

        if len(cells) == 5:
            prev_r = row - dr
            prev_c = col - dc

            next_r = row + dr * 5
            next_c = col + dc * 5

            prev_blocked = False
            next_blocked = False

            if 0 <= prev_r < BOARD_SIZE and 0 <= prev_c < BOARD_SIZE:
                if board[prev_r][prev_c] == opponent:
                    prev_blocked = True

            if 0 <= next_r < BOARD_SIZE and 0 <= next_c < BOARD_SIZE:
                if board[next_r][next_c] == opponent:
                    next_blocked = True

            if prev_blocked and next_blocked:
                continue

            return True

    return False


def check_winner(board, player):
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == player:
                if check_five_from_cell(board, row, col, player):
                    return True
    return False


def is_board_full(board):
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY:
                return False
    return True