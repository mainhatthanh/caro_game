"""Board operations for the Caro game.

Provides board creation, move execution, candidate move generation,
and neighbor detection — all the fundamental board manipulations
that the game logic and AI engine depend on.
"""

from constants import BOARD_SIZE, EMPTY, PLAYER, AI


def create_board():
    """Return a new 15x15 board filled with EMPTY (0)."""
    return [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]


def print_board(board):
    """Print the board to stdout with X for PLAYER, O for AI, . for empty."""
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
    """Place `player` at (row, col) if empty. Returns True on success."""
    if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
        if board[row][col] == EMPTY:
            board[row][col] = player
            return True
    return False


def get_player_move():
    """Read row, col integers from stdin (console game)."""
    while True:
        try:
            row = int(input("Nhap hang (0 - 14): "))
            col = int(input("Nhap cot (0 - 14): "))
            return row, col
        except ValueError:
            print("Vui long nhap so nguyen")


def get_empty_cells(board):
    """Return list of all empty cell coordinates on the board."""
    empty_cells = []

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY:
                empty_cells.append((row, col))

    return empty_cells


def has_neighbor(board, row, col, distance):
    """Check if any stone exists within `distance` cells of (row, col).

    Scans a (2*distance+1)² square centered on (row, col), excluding
    the cell itself. Used by get_candidate_moves to limit search area.
    """
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


def get_candidate_moves(board, distance=2):
    """Return a list of empty cells that are near at least one stone.

    On the empty board, returns the center cell only.
    Otherwise, scans the board for empty cells within `distance` cells
    of any existing stone. This limits the search space dramatically
    (from 225 cells to ~40-80 near stones).

    The results are returned as a shuffled list so search isn't biased
    by scan order (move ordering handles the actual prioritization).
    """
    candidate_moves = []

    # Empty board shortcut: play center
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

    # Collect all empty cells within `distance` of any stone.
    # Uses a set to avoid duplicates (nearby stones have overlapping neighborhoods).
    candidates = set()
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY:
                continue
            # Expand outward `distance` cells from this stone
            for dr in range(-distance, distance + 1):
                for dc in range(-distance, distance + 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = row + dr
                    nc = col + dc
                    if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == EMPTY:
                        candidates.add((nr, nc))

    return list(candidates)
