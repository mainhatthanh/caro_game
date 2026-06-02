import subprocess
import sys
import pytest

from constants import BOARD_SIZE, EMPTY, PLAYER, AI, EASY, MEDIUM, HARD
from board import create_board
from ai import ai_move

CELL_SIZE = 600 // BOARD_SIZE


# ===================== HELPER FUNCTIONS =====================

def swap_board(board):
    """Create a copy of the board with PLAYER and AI values swapped."""
    return [
        [AI if cell == PLAYER else PLAYER if cell == AI else EMPTY
         for cell in row]
        for row in board
    ]


def find_move_for_player(board, level):
    """Find the best move for the PLAYER (X) using the AI engine."""
    swapped = swap_board(board)
    return ai_move(swapped, level)


# ===================== DISPLAY CHECK =====================

def _has_display():
    import tkinter as tk
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except tk.TclError:
        return False

needs_display = pytest.mark.skipif(
    not _has_display(),
    reason="No display available for tkinter"
)


# ===================== SUBPROCESS MATCH =====================

def _run_match_subprocess(level, timeout=120):
    """Run an AI-vs-AI match in a subprocess for clean tkinter isolation.
    Returns (winner, move_count)."""
    script = f"""import threading, time, tkinter as tk, sys
from constants import BOARD_SIZE, EMPTY, PLAYER, AI, EASY, MEDIUM, HARD
from board import create_board, make_move
from rules import check_winner
from ai import ai_move, killer_moves, MAX_DEPTH

CELL_SIZE = 600 // BOARD_SIZE
PAD = CELL_SIZE // 4

def draw_board(canvas, board):
    canvas.delete("all")
    for i in range(BOARD_SIZE + 1):
        x = i * CELL_SIZE
        canvas.create_line(x, 0, x, 600, fill="#555555")
        canvas.create_line(0, x, 600, x, fill="#555555")
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == EMPTY:
                continue
            x1 = c * CELL_SIZE + PAD
            y1 = r * CELL_SIZE + PAD
            x2 = (c + 1) * CELL_SIZE - PAD
            y2 = (r + 1) * CELL_SIZE - PAD
            if board[r][c] == PLAYER:
                canvas.create_line(x1, y1, x2, y2, fill="#00ff88", width=3)
                canvas.create_line(x1, y2, x2, y1, fill="#00ff88", width=3)
            else:
                canvas.create_oval(x1, y1, x2, y2, outline="#ffffff", width=3)

def swap_board(board):
    return [[AI if cell == PLAYER else PLAYER if cell == AI else EMPTY for cell in row] for row in board]

def find_move_for_player(board, level):
    return ai_move(swap_board(board), level)

level = {level}
app = type('App', (), {{}})()
app.root = tk.Tk()
app.root.title("AI vs AI - Caro Game")
app.root.geometry("680x720")
app.root.resizable(False, False)
app.root.configure(bg="#1e1e1e")
app.canvas = tk.Canvas(app.root, width=600, height=600, bg="#2b2b2b", highlightthickness=0)
app.canvas.pack(pady=10)
app.status_label = tk.Label(app.root, text="Starting...", font=("Segoe UI", 12), fg="white", bg="#1e1e1e")
app.status_label.pack()
app.lock = threading.Lock()
app.board = create_board()
app.game_over = False
app.winner = None
app.turn = PLAYER
app.player_sem = threading.Semaphore(1)
app.ai_sem = threading.Semaphore(0)
app.move_count = 0
draw_board(app.canvas, app.board)

def x_thread():
    while not app.game_over:
        app.player_sem.acquire()
        if app.game_over:
            app.ai_sem.release()
            return
        with app.lock:
            snapshot = [row[:] for row in app.board]
            saved_km = {{d: list(killer_moves[d]) for d in range(MAX_DEPTH + 1)}}
        move = find_move_for_player(snapshot, level)
        with app.lock:
            for d in range(MAX_DEPTH + 1):
                killer_moves[d] = saved_km[d]
            if app.game_over:
                app.ai_sem.release()
                return
            if move is None:
                app.game_over = True
                app.ai_sem.release()
                return
            row, col = move
            make_move(app.board, row, col, PLAYER)
            app.move_count += 1
            if check_winner(app.board, PLAYER):
                app.game_over = True
                app.winner = PLAYER
                app.ai_sem.release()
                return
            app.turn = AI
        app.ai_sem.release()

def o_thread():
    while not app.game_over:
        app.ai_sem.acquire()
        if app.game_over:
            app.player_sem.release()
            return
        with app.lock:
            snapshot = [row[:] for row in app.board]
            saved_km = {{d: list(killer_moves[d]) for d in range(MAX_DEPTH + 1)}}
        move = ai_move(snapshot, level)
        with app.lock:
            for d in range(MAX_DEPTH + 1):
                killer_moves[d] = saved_km[d]
            if app.game_over:
                app.player_sem.release()
                return
            if move is None:
                app.game_over = True
                app.player_sem.release()
                return
            row, col = move
            make_move(app.board, row, col, AI)
            app.move_count += 1
            if check_winner(app.board, AI):
                app.game_over = True
                app.winner = AI
                app.player_sem.release()
                return
            app.turn = PLAYER
        app.player_sem.release()

t1 = threading.Thread(target=x_thread, daemon=True)
t2 = threading.Thread(target=o_thread, daemon=True)
t1.start()
t2.start()

start = time.time()
while not app.game_over:
    app.root.update()
    with app.lock:
        snapshot = [row[:] for row in app.board]
        over = app.game_over
        mc = app.move_count
        turn = app.turn
    draw_board(app.canvas, snapshot)
    if over:
        text = f"Game Over - {{mc}} moves"
    else:
        text = f"Move {{mc}} | {{'X' if turn == PLAYER else 'O'}}'s turn"
    app.status_label.config(text=text)
    if time.time() - start > {timeout}:
        with app.lock:
            app.game_over = True
        app.player_sem.release()
        app.ai_sem.release()
        break
    time.sleep(0.05)
app.root.destroy()
t1.join(timeout=5)
t2.join(timeout=5)
print(f"RESULT:{{app.winner}}:{{app.move_count}}")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=timeout + 30,
        cwd=sys.path[0] if sys.path[0] else None
    )
    for line in result.stdout.strip().split("\n"):
        if line.startswith("RESULT:"):
            parts = line[7:].split(":")
            winner_str = parts[0]
            winner = None
            if winner_str == "1":
                winner = PLAYER
            elif winner_str == "-1":
                winner = AI
            move_count = int(parts[1]) if parts[1] else 0
            return winner, move_count
    # Subprocess didn't print RESULT line — likely a crash
    raise RuntimeError(
        f"Match subprocess failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ===================== HELPERS TESTS =====================

class TestSwapBoard:
    def test_swap_board_empty(self):
        board = create_board()
        swapped = swap_board(board)
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                assert swapped[r][c] == EMPTY

    def test_swap_board_swaps_values(self):
        board = create_board()
        board[3][5] = PLAYER
        board[7][7] = AI
        swapped = swap_board(board)
        assert swapped[3][5] == AI
        assert swapped[7][7] == PLAYER
        assert board[3][5] == PLAYER  # original unchanged

    def test_swap_board_keeps_empty(self):
        board = create_board()
        board[5][5] = PLAYER
        swapped = swap_board(board)
        assert swapped[0][0] == EMPTY

    def test_swap_board_is_copy(self):
        board = create_board()
        board[3][3] = PLAYER
        swapped = swap_board(board)
        swapped[3][3] = EMPTY
        assert board[3][3] == PLAYER


class TestFindMoveForPlayer:
    def test_returns_cell_on_empty(self):
        board = create_board()
        move = find_move_for_player(board, EASY)
        assert move is not None
        r, c = move
        assert 0 <= r < BOARD_SIZE
        assert 0 <= c < BOARD_SIZE

    def test_returns_center_on_empty(self):
        board = create_board()
        move = find_move_for_player(board, EASY)
        assert move == (7, 7)

    def test_returns_valid_empty_cell(self):
        board = create_board()
        board[7][7] = AI
        move = find_move_for_player(board, EASY)
        assert move is not None
        r, c = move
        assert board[r][c] == EMPTY


# ===================== SIMULATION MATCH TESTS =====================

class TestSimulation:
    @needs_display
    def test_easy_vs_easy(self):
        winner, move_count = _run_match_subprocess(EASY, timeout=120)
        assert move_count >= 1
        assert winner in (PLAYER, AI, None)

    @needs_display
    def test_medium_vs_medium(self):
        winner, move_count = _run_match_subprocess(MEDIUM, timeout=120)
        assert move_count >= 1
        assert winner in (PLAYER, AI, None)

    @needs_display
    def test_hard_vs_hard(self):
        winner, move_count = _run_match_subprocess(HARD, timeout=120)
        assert move_count >= 1
        assert winner in (PLAYER, AI, None)
