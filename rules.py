"""Win detection and board-full check for Caro.

Provides two win-checking strategies:
1. Full board scan (O(n²)) — for terminal check in evaluation
2. Last-move-only scan (O(depth)) — fast check during search,
   only examines lines through the most-recently-placed stone
"""

from constants import BOARD_SIZE, EMPTY, PLAYER, AI


def check_five_from_cell(board, row, col, player):
    """Check if `player` has exactly 5 in a row through (row, col).

    Scans in 4 directions from the cell. Only counts sequences where
    both ends are NOT blocked by the opponent (a walled 5 doesn't win).

    Used by check_winner() for full-board scan.
    """
    directions = [
        (0, 1),   # horizontal
        (1, 0),   # vertical
        (1, 1),   # diagonal ↘
        (1, -1),  # anti-diagonal ↙
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
            # Check both ends — if both blocked by opponent, this 5 doesn't count
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
    """Full-board scan: check if `player` has a winning line anywhere.

    Slow (O(n²)) but authoritative. Used for terminal checks outside
    the search tree where we don't have a last_move hint.
    """
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == player:
                if check_five_from_cell(board, row, col, player):
                    return True
    return False


def is_board_full(board):
    """Return True if every cell on the board is occupied (draw)."""
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY:
                return False
    return True


def check_five_from_cell_bidirectional(board, row, col, player):
    """Check if there are 5+ of `player` stones in a line through (row, col).

    Unlike check_five_from_cell which looks for EXACTLY 5, this scans
    in both directions from the cell and counts ALL contiguous stones.
    Returns True if count >= 5. Does NOT require open ends.

    This is the fast-path win check used during search — it only examines
    the lines passing through the last-placed stone.
    """
    directions = [
        (0, 1),   # horizontal
        (1, 0),   # vertical
        (1, 1),   # diagonal ↘
        (1, -1),  # anti-diagonal ↙
    ]
    for dr, dc in directions:
        count = 1  # the cell itself
        # Scan forward along the direction
        r, c = row + dr, col + dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
            count += 1
            r += dr
            c += dc
        # Scan backward (opposite direction)
        r, c = row - dr, col - dc
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
            count += 1
            r -= dr
            c -= dc
        if count >= 5:
            return True
    return False


def check_winner_fast(board, player, last_move):
    """Fast win check: only scan lines through `last_move`.

    This is O(k) where k is the stone count per direction (max ~9 per axis),
    vs O(n²) for a full board scan. Used extensively in minimax since we
    always know which cell was just played.

    Falls back to full scan if last_move is None.
    """
    if last_move is None:
        return check_winner(board, player)
    row, col = last_move
    return check_five_from_cell_bidirectional(board, row, col, player)
