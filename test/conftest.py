import pytest
from constants import BOARD_SIZE, PLAYER, AI
from board import create_board
from ai import killer_moves, MAX_DEPTH, history_score
from zobrist import tt_clear


@pytest.fixture
def empty_board():
    return create_board()


@pytest.fixture
def center_move():
    return (7, 7)


@pytest.fixture
def board_horizontal_win():
    board = create_board()
    for col in range(5):
        board[7][col] = PLAYER
    return board


@pytest.fixture
def board_vertical_win():
    board = create_board()
    for row in range(5):
        board[row][7] = AI
    return board


@pytest.fixture
def board_diagonal_win():
    board = create_board()
    for i in range(5):
        board[i][i] = PLAYER
    return board


@pytest.fixture
def board_anti_diagonal_win():
    board = create_board()
    for i in range(5):
        board[i][BOARD_SIZE - 1 - i] = AI
    return board


@pytest.fixture
def board_nearly_full():
    board = create_board()
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if r == 7 and c == 7:
                continue
            board[r][c] = PLAYER if (r + c) % 2 == 0 else AI
    return board


@pytest.fixture
def full_board():
    board = create_board()
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            board[r][c] = PLAYER if (r + c) % 2 == 0 else AI
    return board


@pytest.fixture
def board_ai_advantage():
    board = create_board()
    for col in range(4):
        board[7][col] = AI
    return board


@pytest.fixture
def board_blocked_five():
    board = create_board()
    for col in range(1, 6):
        board[7][col] = PLAYER
    board[7][0] = AI
    board[7][6] = AI
    return board


@pytest.fixture(autouse=True)
def reset_killer_moves():
    saved = {}
    for d in range(MAX_DEPTH + 1):
        saved[d] = list(killer_moves.get(d, []))

    saved_history = [row[:] for row in history_score]

    yield

    for d in range(MAX_DEPTH + 1):
        killer_moves[d] = list(saved.get(d, []))

    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            history_score[r][c] = saved_history[r][c]
    tt_clear()
