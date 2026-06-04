"""Caro AI Tournament Simulation App.

Standalone tkinter GUI for running AI-vs-AI matches with per-AI feature toggles,
softmax-based randomness, parallel subprocess execution, live board display,
post-game replay, and detailed logging to disk.

Usage:
    python simulation/simulate.py

Architecture:
    - Each match runs in its own multiprocessing.Process (spawn start method).
    - Display events stream through a multiprocessing.Queue for live updates.
    - Results are written per-match as .log files and aggregated as summary.json.

Feature toggles allow fine-grained ablation testing (e.g., "what happens
if we disable the transposition table?").

Board display:
    - Black circles (●) = PLAYER (1) — drawn as filled black ovals
    - White circles (○) = AI (-1) — drawn as white ovals with black outline
    - Red dot on the last move
    - Label shows both AI names with their respective stone colors

swap_board():
    The AI engine always evaluates as AI (-1). When it needs to play as
    PLAYER (1), the board is mirrored so the engine's evaluation is correct.
    This is the key fix that was missing from the original implementation.
"""

import sys
import math
import random
import time
import json
import traceback
import multiprocessing
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from queue import Empty as QueueEmpty
import tkinter as tk
from tkinter import ttk

# Ensure the project root is on the path so subprocesses can find modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEATURE_NAMES = [
    "Zobrist/TT",
    "Iterative Deepening",
    "LMR",
    "Candidate Limiting",
    "Killer Heuristic",
    "Move Ordering",
    "Threat Detection",
]

FEATURE_ATTRS = {
    "Zobrist/TT": "zobrist",
    "Iterative Deepening": "iterative_deepening",
    "LMR": "lmr",
    "Candidate Limiting": "candidate_limiting",
    "Killer Heuristic": "killer_heuristic",
    "Move Ordering": "move_ordering",
    "Threat Detection": "threat_detection",
}

BOARD_SIZE = 15

# ---------------------------------------------------------------------------
# Data model — holds feature toggles and search params for one AI
# ---------------------------------------------------------------------------

@dataclass
class AIConfig:
    """Configuration for one AI player in the simulation.

    All fields have defaults matching the "fully enabled" baseline.
    """
    name: str = "AI"
    depth: int = 5
    zobrist: bool = True
    iterative_deepening: bool = True
    lmr: bool = True
    candidate_limiting: bool = True
    killer_heuristic: bool = True
    move_ordering: bool = True
    threat_detection: bool = True
    softmax_temp: float = 0.0

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Softmax helper (no numpy dependency)
# ---------------------------------------------------------------------------

def softmax_sample(ordered, temperature):
    """Pick from an ordered list with exponential decay by rank.

    The top-ranked item has the highest probability. Temperature controls
    how sharp the distribution is:
        temperature=0   -> always pick index 0 (deterministic)
        temperature=inf -> uniform random
        temperature=0.5 -> moderate randomness favoring higher ranks

    This is used to add controlled randomness to AI play (for variety
    in simulations) without resorting to purely random moves.
    """
    n = len(ordered)
    if n == 0:
        return None
    if temperature <= 0 or n == 1:
        return ordered[0]
    weights = [math.exp((n - i - 1) / max(temperature, 1e-9)) for i in range(n)]
    total = sum(weights)
    r = random.random() * total
    cumulative = 0.0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return ordered[i]
    return ordered[-1]


# ---------------------------------------------------------------------------
# Match runner — executes in a subprocess
# ---------------------------------------------------------------------------

# Globals to cache original ai module functions (one per subprocess)
# These let us restore the original implementation when a toggle is re-enabled.
_ORIGINAL_ADD_KILLER = None
_ORIGINAL_ORDER_MOVES = None
_ORIGINAL_COMPUTE_ZOBRIST = None
_ORIGINAL_FIND_BEST = None


def _capture_originals(ai_mod):
    """Save references to the original ai module functions before monkey-patching.

    Called once per subprocess at the start of each match. The saved references
    are used by _apply_config_to_module to restore a feature when its toggle is ON.
    """
    global _ORIGINAL_ADD_KILLER, _ORIGINAL_ORDER_MOVES, _ORIGINAL_COMPUTE_ZOBRIST, _ORIGINAL_FIND_BEST
    _ORIGINAL_ADD_KILLER = ai_mod.add_killer_move
    _ORIGINAL_ORDER_MOVES = ai_mod.order_moves
    _ORIGINAL_COMPUTE_ZOBRIST = ai_mod.compute_zobrist
    _ORIGINAL_FIND_BEST = ai_mod.find_best_move_by_minimax


def swap_board(board):
    """Create a copy of the board with PLAYER and AI values swapped.

    The AI engine always evaluates positions as AI (-1). When it needs to
    play as PLAYER (1), we mirror the board so the engine sees PLAYER stones
    as its own AI stones (and vice versa). This avoids duplicating the
    entire AI pipeline for the other side.
    """
    from constants import EMPTY, PLAYER, AI
    return [
        [AI if cell == PLAYER else PLAYER if cell == AI else EMPTY
         for cell in row]
        for row in board
    ]


def _apply_config_to_module(ai_mod, cfg):
    """Monkey-patch the ai module globals to match the given config.

    Each feature toggle replaces the corresponding function or constant
    with either a no-op (feature OFF) or the original implementation
    (feature ON). This avoids modifying ai.py while still allowing
    per-AI feature configuration at runtime.

    The swap is fast because it only changes function references, not
    the board state or search tree.
    """
    ai_mod.MAX_DEPTH = cfg.depth

    # LMR: ON = threshold at 3, OFF = threshold at 99 (effectively disabled)
    if not cfg.lmr:
        ai_mod.LMR_DEPTH_THRESHOLD = 99
    else:
        ai_mod.LMR_DEPTH_THRESHOLD = 3

    # Candidate limiting: ON = normal caps, OFF = no effective cap (999)
    if not cfg.candidate_limiting:
        ai_mod.CANDIDATE_LIMIT_EARLY = 999
        ai_mod.CANDIDATE_LIMIT_MID = 999
        ai_mod.CANDIDATE_LIMIT_DEEP = 999
    else:
        from constants import CANDIDATE_LIMIT_EARLY, CANDIDATE_LIMIT_MID, CANDIDATE_LIMIT_DEEP
        ai_mod.CANDIDATE_LIMIT_EARLY = CANDIDATE_LIMIT_EARLY
        ai_mod.CANDIDATE_LIMIT_MID = CANDIDATE_LIMIT_MID
        ai_mod.CANDIDATE_LIMIT_DEEP = CANDIDATE_LIMIT_DEEP

    # Killer heuristic: OFF = no-op lambda
    if not cfg.killer_heuristic:
        ai_mod.add_killer_move = lambda depth, move: None
    else:
        if _ORIGINAL_ADD_KILLER is not None:
            ai_mod.add_killer_move = _ORIGINAL_ADD_KILLER

    # Move ordering: OFF = random shuffle
    if not cfg.move_ordering:
        ai_mod.order_moves = (lambda board, cand, player, depth,
                               hash_move=None, opponent=None:
                               random.sample(cand, len(cand)))
    else:
        if _ORIGINAL_ORDER_MOVES is not None:
            ai_mod.order_moves = _ORIGINAL_ORDER_MOVES

    # Zobrist: OFF = compute_zobrist returns None (disables TT)
    if not cfg.zobrist:
        ai_mod.compute_zobrist = lambda board: None
    else:
        if _ORIGINAL_COMPUTE_ZOBRIST is not None:
            ai_mod.compute_zobrist = _ORIGINAL_COMPUTE_ZOBRIST

    # Threat detection: OFF = bypass pre-search pipeline entirely
    if not cfg.threat_detection:
        ai_mod.find_best_move_by_minimax = ai_mod._iterative_deepening_search
    else:
        if _ORIGINAL_FIND_BEST is not None:
            ai_mod.find_best_move_by_minimax = _ORIGINAL_FIND_BEST


def _get_move_with_config(board, cfg, ai_mod, player):
    """Get the best move for `player` using the given config.

    The core insight: the AI engine always evaluates as AI (-1). When
    the engine should play as PLAYER (1), we call swap_board() so the
    engine sees the opponent's stones as its own.

    After the move is chosen, softmax re-picking can inject controlled
    randomness for variety in simulations.
    """
    from constants import EMPTY, PLAYER, AI
    from board import get_candidate_moves

    candidate_moves = get_candidate_moves(board, 1)
    if not candidate_moves:
        return None

    # swap_board: the engine always evaluates as AI (-1)
    work_board = swap_board(board) if player == PLAYER else board

    # find_best_move_by_minimax includes the full pre-search pipeline.
    # When threat_detection=False, it's monkey-patched to call
    # _iterative_deepening_search instead (bypasses threat scanning).
    move = ai_mod.find_best_move_by_minimax(work_board, cfg.depth)
    if move is None:
        return None

    # Softmax re-pick for controlled randomness
    if cfg.softmax_temp > 0:
        ordered = candidate_moves
        if cfg.move_ordering:
            ordered = ai_mod.order_moves(board, ordered, -1, cfg.depth)
        result = softmax_sample(ordered[:20], cfg.softmax_temp)
        return result if result is not None else move

    return move


def _write_match_log(filepath, result):
    """Write a human-readable match log file.

    Log format:
      === Match 000 ===
      AI1: AI1 | AI2: AI2
      AI1 first: True
      AI1 config: {...}
      AI2 config: {...}

        Move #  1 (AI1       ): ( 7, 7)  0.005s
        Move #  2 (AI2       ): ( 8, 8)  0.032s
        ...
        Move # 21 (AI1       ): (10,11)  0.001s [W]

      === RESULT: AI1 ===
      Moves: 21
      AI1 total time: 0.058s  (avg: 0.006s)
      AI2 total time: 3.876s  (avg: 0.388s)
      Total elapsed: 3.935s

    The [W] marker indicates the winning move.
    """
    lines = []
    lines.append(f"=== Match {result['match_id']:03d} ===")
    lines.append(f"AI1: {result['ai1_name']} | AI2: {result['ai2_name']}")
    lines.append(f"AI1 first: {result['ai1_first']}")
    lines.append(f"AI1 config: {json.dumps(result['ai1_config'])}")
    lines.append(f"AI2 config: {json.dumps(result['ai2_config'])}")
    lines.append("")

    if result["ai1_first"]:
        board_map = {-1: result["ai1_name"], 1: result["ai2_name"]}
    else:
        board_map = {-1: result["ai2_name"], 1: result["ai1_name"]}

    for i, (row, col, player, t) in enumerate(result["move_log"], 1):
        name = board_map.get(player, "?")
        mark = " [W]" if i == len(result["move_log"]) and result["winner"] != "draw" else ""
        lines.append(f"  Move #{i:3d} ({name:10s}): ({row:2d},{col:2d})  {t:.3f}s{mark}")

    lines.append("")
    lines.append(f"=== RESULT: {result['winner']} ===")
    lines.append(f"Moves: {result['moves']}")
    lines.append(f"AI1 total time: {result['ai1_time']:.3f}s  "
                 f"(avg: {result['ai1_time']/max(result['moves']//2,1):.3f}s)")
    lines.append(f"AI2 total time: {result['ai2_time']:.3f}s  "
                 f"(avg: {result['ai2_time']/max(result['moves']//2,1):.3f}s)")
    lines.append(f"Total elapsed: {result['total_time']:.3f}s")

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            f.write("\n".join(lines))
    except Exception as e:
        print(f"ERROR writing match log {filepath}: {e}", file=sys.stderr)


def run_match(match_id, ai1_cfg_dict, ai2_cfg_dict,
              ai1_softmax, ai2_softmax, ai1_first,
              display_queue, result_queue, log_dir, error_file):
    """Entry point for a single match subprocess.

    All arguments must be picklable (since we use spawn start method).
    Modules are imported inside the process to ensure fresh state.

    Errors are written to error_file (not stdout) so they don't interfere
    with queue communication.
    """
    try:
        _run_match_inner(match_id, ai1_cfg_dict, ai2_cfg_dict,
                         ai1_softmax, ai2_softmax, ai1_first,
                         display_queue, result_queue, log_dir)
    except Exception as exc:
        tb = traceback.format_exc()
        try:
            with open(error_file, "a") as f:
                f.write(f"[Match {match_id}] ERROR: {exc}\n{tb}\n")
        except Exception:
            pass


def _run_match_inner(match_id, ai1_cfg_dict, ai2_cfg_dict,
                     ai1_softmax, ai2_softmax, ai1_first,
                     display_queue, result_queue, log_dir):
    """Inner function — exceptions propagate to run_match's handler.

    Game loop:
    1. Apply feature toggles for current player's AI
    2. Get move via _get_move_with_config (with swap_board if needed)
    3. Place stone on board
    4. Send display event to GUI
    5. Check for win
    6. Switch player

    The engine evaluates the board as AI (-1) internally, and swap_board
    handles the case where the engine needs to play as PLAYER (1).
    """
    # Imports (fresh per subprocess via spawn)
    import sys as _sys
    _sys.path.insert(0, str(PROJECT_ROOT))
    from board import create_board
    from rules import check_winner_fast
    import ai as _ai
    from constants import EMPTY, PLAYER, AI

    # Capture original ai module functions before monkey-patching
    _capture_originals(_ai)

    # Build config objects
    ai1_cfg_dict["softmax_temp"] = ai1_softmax
    ai2_cfg_dict["softmax_temp"] = ai2_softmax
    ai1_cfg = AIConfig(**ai1_cfg_dict)
    ai2_cfg = AIConfig(**ai2_cfg_dict)

    # Map which AI plays which side based on ai1_first
    if ai1_first:
        player_to_name = {AI: ai1_cfg.name, PLAYER: ai2_cfg.name}
        player_to_cfg = {AI: ai1_cfg, PLAYER: ai2_cfg}
    else:
        player_to_name = {AI: ai2_cfg.name, PLAYER: ai1_cfg.name}
        player_to_cfg = {AI: ai2_cfg, PLAYER: ai1_cfg}

    board = create_board()
    move_log = []
    start_time = time.time()
    current_player = PLAYER  # PLAYER always moves first
    ai1_accum = 0.0
    ai2_accum = 0.0
    winner = "draw"

    for move_num in range(1, 226):  # max 225 moves on 15x15
        cfg = player_to_cfg[current_player]
        name = player_to_name[current_player]
        is_ai1_side = (current_player == AI and ai1_first) or (current_player == PLAYER and not ai1_first)

        # Apply feature toggles for this AI
        _apply_config_to_module(_ai, cfg)

        # Get move — swap_board happens inside if player == PLAYER
        move_start = time.time()
        move = _get_move_with_config(board, cfg, _ai, current_player)
        move_time = time.time() - move_start

        if is_ai1_side:
            ai1_accum += move_time
        else:
            ai2_accum += move_time

        if move is None:
            winner = "draw"
            break

        row, col = move
        move_log.append((row, col, current_player, move_time))

        # Place stone
        board[row][col] = current_player

        # Send display event (non-blocking — drop if queue full to avoid blocking)
        display_event = {
            "type": "move",
            "match_id": match_id,
            "move_num": move_num,
            "row": row,
            "col": col,
            "player": current_player,
            "ai1_name": ai1_cfg.name,
            "ai2_name": ai2_cfg.name,
            "ai1_first": ai1_first,
        }
        try:
            display_queue.put_nowait(display_event)
        except Exception:
            pass

        # Check win
        if check_winner_fast(board, current_player, (row, col)):
            winner = name
            try:
                display_queue.put_nowait({
                    "type": "win",
                    "match_id": match_id,
                    "move_num": move_num,
                    "row": row,
                    "col": col,
                    "player": current_player,
                    "winner": winner,
                    "ai1_name": ai1_cfg.name,
                    "ai2_name": ai2_cfg.name,
                    "ai1_first": ai1_first,
                })
            except Exception:
                pass
            break

        # Switch player for next turn
        current_player = PLAYER if current_player == AI else AI

    elapsed = time.time() - start_time

    # Build result dict
    result = {
        "match_id": match_id,
        "winner": winner,
        "moves": len(move_log),
        "ai1_name": ai1_cfg.name,
        "ai2_name": ai2_cfg.name,
        "ai1_first": ai1_first,
        "ai1_time": ai1_accum,
        "ai2_time": ai2_accum,
        "total_time": elapsed,
        "ai1_config": ai1_cfg.to_dict(),
        "ai2_config": ai2_cfg.to_dict(),
        "move_log": move_log,
    }

    # Write per-match log file
    log_path = Path(log_dir)
    match_file = log_path / f"match_{match_id:03d}.log"
    _write_match_log(match_file, result)

    # Send result to GUI
    try:
        result_queue.put_nowait(result)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# GUI — Tkinter tournament controller
# ---------------------------------------------------------------------------

class SimulationGUI:
    """Main tkinter window for the tournament simulation.

    Layout (horizontal paned window):
    ┌─────────────────────┬─────────────────────────────┐
    │ AI1 Config          │ Board Display               │
    │ AI2 Config          │ Stats Panel                 │
    │ Controls            │ Log Output                  │
    └─────────────────────┴─────────────────────────────┘

    Lifecycle:
    start_simulation → spawn N processes → poll_queues (every 200ms)
    → drain display events → drain results → update stats
    → _finish_tournament when all matches complete
    """

    CELL_SIZE = 30
    BOARD_PX = BOARD_SIZE * CELL_SIZE
    STONE_RADIUS = 12

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Caro AI Tournament")
        self.root.geometry("1920x1080")

        # Multiprocessing state
        self.processes = []
        self.running = False
        self.display_queue = multiprocessing.Queue(maxsize=5000)
        self.result_queue = multiprocessing.Queue()

        # Display state
        self.display_match_id = None
        self.display_moves = []
        self.display_match_label_str = tk.StringVar(value="No match selected")
        self.active_match_ids = set()
        self.completed_match_ids = set()
        self.completed_count = 0

        # Replay state
        self.replay_active = False
        self.replay_paused = False
        self.replay_index = 0
        self.replay_speed = tk.DoubleVar(value=0.3)

        # Stats tracking
        self.match_results = []
        self.match_move_buffers = {}
        self.match_meta = {}
        self.stats_vars = {}

        # Session timestamp + log directory
        self.session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir = PROJECT_ROOT / "simulation" / "logs" / self.session_ts
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.error_file = self.log_dir / "errors.log"

        self._build_ui()
        self._poll_queues()

    # ===================== UI BUILD =====================

    def _build_ui(self):
        """Build the main window with a horizontal PanedWindow split."""
        main_pw = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pw.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_pw)
        main_pw.add(left_frame, weight=0)

        self._build_config_panel(left_frame, 1)
        self._build_config_panel(left_frame, 2)
        self._build_controls(left_frame)

        right_frame = ttk.Frame(main_pw)
        main_pw.add(right_frame, weight=1)

        self._build_board_display(right_frame)
        self._build_stats_panel(right_frame)
        self._build_log_panel(right_frame)

    def _build_config_panel(self, parent, ai_num):
        """Build the configuration panel for one AI with name, feature toggles,
        depth spinner, and softmax controls."""
        lbl = f"AI {ai_num} Configuration"
        frame = ttk.LabelFrame(parent, text=lbl, padding=5)
        frame.pack(fill=tk.X, pady=(0, 5))

        # Name
        nf = ttk.Frame(frame)
        nf.pack(fill=tk.X, pady=2)
        ttk.Label(nf, text="Name:").pack(side=tk.LEFT)
        name_var = tk.StringVar(value=f"AI{ai_num}")
        ttk.Entry(nf, textvariable=name_var, width=15).pack(side=tk.LEFT, padx=(5, 0))
        setattr(self, f"ai{ai_num}_name", name_var)

        # Feature checkboxes (2 columns)
        cf = ttk.Frame(frame)
        cf.pack(fill=tk.X, pady=2)
        cb_vars = {}
        for i, fname in enumerate(FEATURE_NAMES):
            var = tk.BooleanVar(value=True)
            attr = FEATURE_ATTRS[fname]
            cb = ttk.Checkbutton(cf, text=fname, variable=var)
            cb.grid(row=i // 2, column=i % 2, sticky=tk.W, padx=(0, 10))
            cb_vars[attr] = var
        setattr(self, f"ai{ai_num}_features", cb_vars)

        # Depth
        df = ttk.Frame(frame)
        df.pack(fill=tk.X, pady=2)
        ttk.Label(df, text="Depth:").pack(side=tk.LEFT)
        depth_var = tk.IntVar(value=5)
        ttk.Spinbox(df, from_=1, to=5, textvariable=depth_var, width=4).pack(side=tk.LEFT, padx=(5, 0))
        setattr(self, f"ai{ai_num}_depth", depth_var)

        # Softmax temperature
        sf = ttk.Frame(frame)
        sf.pack(fill=tk.X, pady=2)
        ttk.Label(sf, text="Softmax:").pack(side=tk.LEFT)
        sm_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(sf, from_=0.0, to=2.0, increment=0.1,
                     textvariable=sm_var, width=5).pack(side=tk.LEFT, padx=(5, 0))
        sm_rnd = tk.BooleanVar(value=False)
        ttk.Checkbutton(sf, text="Rand/match",
                        variable=sm_rnd).pack(side=tk.LEFT, padx=(10, 0))
        setattr(self, f"ai{ai_num}_softmax", sm_var)
        setattr(self, f"ai{ai_num}_softmax_randomize", sm_rnd)

    def _build_controls(self, parent):
        """Build the control panel: match count, parallelism, Start/Stop buttons."""
        frame = ttk.LabelFrame(parent, text="Controls", padding=5)
        frame.pack(fill=tk.X, pady=(0, 5))

        mf = ttk.Frame(frame)
        mf.pack(fill=tk.X, pady=2)
        ttk.Label(mf, text="Matches:").pack(side=tk.LEFT)
        self.match_count_var = tk.IntVar(value=10)
        ttk.Spinbox(mf, from_=1, to=200, textvariable=self.match_count_var, width=5).pack(side=tk.LEFT, padx=(5, 0))

        pf = ttk.Frame(frame)
        pf.pack(fill=tk.X, pady=2)
        ttk.Label(pf, text="Parallel:").pack(side=tk.LEFT)
        cpu_count = multiprocessing.cpu_count()
        self.parallel_var = tk.IntVar(value=min(4, cpu_count))
        ttk.Spinbox(pf, from_=1, to=cpu_count, textvariable=self.parallel_var, width=5).pack(side=tk.LEFT, padx=(5, 0))

        bf = ttk.Frame(frame)
        bf.pack(fill=tk.X, pady=(5, 0))
        self.start_btn = ttk.Button(bf, text="Start", command=self.start_simulation)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.stop_btn = ttk.Button(bf, text="Stop", command=self.stop_simulation, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

    def _build_board_display(self, parent):
        """Build the board canvas with match label, move count, switch/replay controls.

        The board draws:
        - Black filled ovals for PLAYER (1)
        - White ovals with black outline for AI (-1)
        - Red dot on the most recent move
        - Coordinate labels on the edges

        Below the board: Switch Display, Replay, Speed slider, Pause button.
        """
        frame = ttk.LabelFrame(parent, text="Live Match", padding=5)
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.match_label = ttk.Label(frame, textvariable=self.display_match_label_str,
                                     font=("", 10, "bold"))
        self.match_label.pack()

        self.move_count_var = tk.StringVar(value="Moves: 0")
        ttk.Label(frame, textvariable=self.move_count_var).pack()

        canvas_f = ttk.Frame(frame)
        canvas_f.pack(pady=5)
        self.canvas = tk.Canvas(canvas_f, width=self.BOARD_PX + 40,
                                height=self.BOARD_PX + 40,
                                bg="#DEB887", highlightthickness=0)
        self.canvas.pack()
        self._draw_board_grid()

        bf = ttk.Frame(frame)
        bf.pack(pady=(2, 0))
        self.switch_btn = ttk.Button(bf, text="Switch Display",
                                     command=self._switch_display,
                                     state=tk.DISABLED)
        self.switch_btn.pack(side=tk.LEFT, padx=5)
        self.replay_btn = ttk.Button(bf, text="Replay",
                                     command=self._start_replay,
                                     state=tk.DISABLED)
        self.replay_btn.pack(side=tk.LEFT, padx=5)

        rf = ttk.Frame(frame)
        rf.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(rf, text="Speed:").pack(side=tk.LEFT)
        self.replay_slider = ttk.Scale(rf, from_=0.05, to=1.0,
                                       orient=tk.HORIZONTAL,
                                       variable=self.replay_speed,
                                       state=tk.DISABLED)
        self.replay_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Label(rf, textvariable=self.replay_speed, width=4).pack(side=tk.LEFT)
        self.pause_btn = ttk.Button(rf, text="Pause",
                                     command=self._toggle_pause_replay,
                                     state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)

    def _draw_board_grid(self):
        """Draw the 15x15 board grid lines along with coordinate labels.

        Uses the "grid" tag so the grid can be deleted/redrawn independently
        of stones (which use the "stone" tag).
        """
        offset = 20
        size = self.BOARD_PX
        self.canvas.delete("grid")
        for i in range(BOARD_SIZE):
            x = offset + i * self.CELL_SIZE
            self.canvas.create_line(x, offset, x, offset + size, fill="#333", tags="grid")
            y = offset + i * self.CELL_SIZE
            self.canvas.create_line(offset, y, offset + size, y, fill="#333", tags="grid")
        for i in range(BOARD_SIZE):
            x = offset + i * self.CELL_SIZE
            self.canvas.create_text(x, offset - 12, text=str(i), font=("", 7), tags="grid")
            y = offset + i * self.CELL_SIZE
            self.canvas.create_text(offset - 12, y, text=str(i), font=("", 7), tags="grid")

    def _redraw_board(self):
        """Redraw all stones on the board from the display_moves buffer.

        PLAYER (1) = black filled oval
        AI (-1)    = white oval with black outline
        Last move  = small red dot at center

        The display_moves list stores (row, col, player) tuples in
        chronological order. Each call fully redraws the board from scratch.
        """
        self.canvas.delete("stone")
        offset = 20
        for row, col, player in self.display_moves:
            x = offset + col * self.CELL_SIZE
            y = offset + row * self.CELL_SIZE
            r = self.STONE_RADIUS
            if player == 1:
                self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                        fill="black", tags="stone")
            else:
                self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                        fill="white", outline="black", width=1.5,
                                        tags="stone")
        # Red dot on the last move
        if self.display_moves:
            lr, lc, _ = self.display_moves[-1]
            lx = offset + lc * self.CELL_SIZE
            ly = offset + lr * self.CELL_SIZE
            self.canvas.create_oval(lx - 3, ly - 3, lx + 3, ly + 3,
                                    fill="red", tags="stone")

    def _build_stats_panel(self, parent):
        """Build the statistics panel showing match results and timing."""
        frame = ttk.LabelFrame(parent, text="Statistics", padding=5)
        frame.pack(fill=tk.X, pady=(0, 5))

        stats = [
            ("Total Matches", "total"),
            ("Completed", "completed"),
            ("AI1 Wins", "ai1_wins"),
            ("AI2 Wins", "ai2_wins"),
            ("Draws", "draws"),
            ("AI1 Avg Move Time", "ai1_avg_time"),
            ("AI2 Avg Move Time", "ai2_avg_time"),
            ("AI1 Win Rate", "ai1_winrate"),
            ("AI2 Win Rate", "ai2_winrate"),
        ]
        for i, (label, key) in enumerate(stats):
            var = tk.StringVar(value="—")
            ttk.Label(frame, text=f"{label}:", width=18, anchor=tk.E).grid(
                row=i, column=0, sticky=tk.E, padx=(0, 5))
            ttk.Label(frame, textvariable=var, width=12, anchor=tk.W).grid(
                row=i, column=1, sticky=tk.W)
            self.stats_vars[key] = var

    def _build_log_panel(self, parent):
        """Build a scrollable text log panel at the bottom of the right pane."""
        frame = ttk.LabelFrame(parent, text="Log Output", padding=5)
        frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(frame, height=8, width=50, wrap=tk.WORD,
                                font=("Consolas", 9))
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _read_ai_config(self, ai_num):
        """Read the current UI field values for one AI into a config dict."""
        name = getattr(self, f"ai{ai_num}_name").get()
        depth = getattr(self, f"ai{ai_num}_depth").get()
        softmax = getattr(self, f"ai{ai_num}_softmax").get()
        randomize = getattr(self, f"ai{ai_num}_softmax_randomize").get()
        features = getattr(self, f"ai{ai_num}_features")
        cfg = {
            "name": name,
            "depth": depth,
            "zobrist": features["zobrist"].get(),
            "iterative_deepening": features["iterative_deepening"].get(),
            "lmr": features["lmr"].get(),
            "candidate_limiting": features["candidate_limiting"].get(),
            "killer_heuristic": features["killer_heuristic"].get(),
            "move_ordering": features["move_ordering"].get(),
            "threat_detection": features["threat_detection"].get(),
        }
        return cfg, softmax, randomize

    # ===================== SIMULATION CONTROL =====================

    def start_simulation(self):
        """Start a new tournament with the current configuration.

        Spawns N subprocesses (one per match), alternating who plays first.
        Matches are spawned up to the parallel limit. The OS schedules them.
        """
        if self.running:
            return

        self.running = True
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.switch_btn.configure(state=tk.NORMAL)
        self.replay_active = False
        self.replay_paused = False
        self.replay_btn.configure(state=tk.DISABLED)
        self.replay_slider.configure(state=tk.DISABLED)
        self.pause_btn.configure(state=tk.DISABLED)
        self.completed_count = 0
        self.match_results = []
        self.match_move_buffers = {}
        self.match_meta = {}
        self.match_softmax_values = {}
        self.active_match_ids = set()
        self.processes = []
        self.display_match_id = None
        self.display_moves = []
        self._redraw_board()

        ai1_cfg_dict, ai1_softmax, ai1_rand = self._read_ai_config(1)
        ai2_cfg_dict, ai2_softmax, ai2_rand = self._read_ai_config(2)

        num_matches = self.match_count_var.get()
        parallel = self.parallel_var.get()

        self._log(f"Starting {num_matches} matches ({parallel} parallel)...")
        self._log(f"  AI1: {ai1_cfg_dict['name']} depth={ai1_cfg_dict['depth']} "
                  f"softmax={'random' if ai1_rand else f'{ai1_softmax:.1f}'}")
        self._log(f"  AI2: {ai2_cfg_dict['name']} depth={ai2_cfg_dict['depth']} "
                  f"softmax={'random' if ai2_rand else f'{ai2_softmax:.1f}'}")
        self._log(f"  Error log: {self.error_file}")

        # Clear old error log
        try:
            self.error_file.write_text("")
        except Exception:
            pass

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Spawn subprocesses — OS handles parallelism limits
        for mid in range(num_matches):
            # Alternate who plays first (odd = AI1 first, even = AI2 first)
            ai1_first = (mid % 2 == 0)
            sm1 = random.uniform(0, ai1_softmax) if ai1_rand else ai1_softmax
            sm2 = random.uniform(0, ai2_softmax) if ai2_rand else ai2_softmax

            p = multiprocessing.Process(
                target=run_match,
                args=(mid, ai1_cfg_dict, ai2_cfg_dict,
                      sm1, sm2, ai1_first,
                      self.display_queue, self.result_queue,
                      str(self.log_dir), str(self.error_file)),
                daemon=True,
            )
            p.start()
            self.processes.append(p)
            self.active_match_ids.add(mid)
            self.match_move_buffers[mid] = []
            self.match_softmax_values[mid] = (sm1, sm2)

        self.stats_vars["total"].set(str(num_matches))
        self._log(f"Started {num_matches} matches. Logs: {self.log_dir}")

    def stop_simulation(self):
        """Terminate all running match subprocesses."""
        if not self.running:
            return
        self._log("Stopping...")
        self.running = False
        for p in self.processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=1)
        self.processes.clear()
        self.active_match_ids.clear()
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.switch_btn.configure(state=tk.DISABLED)
        self._log("Stopped.")

    # ===================== QUEUE POLLING (event loop) =====================

    def _poll_queues(self):
        """Poll display and result queues every 200ms.

        This is the main event processing loop, called via root.after().

        1. Drain display queue → update live board if current match
        2. Drain result queue → update stats, log completion
        3. Check for crashed subprocesses
        4. If all done, call _finish_tournament()
        """
        if self.running:
            # ----- Drain display events -----
            try:
                while True:
                    ev = self.display_queue.get_nowait()
                    mid = ev["match_id"]
                    if mid not in self.active_match_ids:
                        continue

                    # Buffer ALL moves and metadata for every match
                    if mid not in self.match_move_buffers:
                        self.match_move_buffers[mid] = []
                        self.match_meta[mid] = {
                            "ai1_name": ev["ai1_name"],
                            "ai2_name": ev["ai2_name"],
                            "ai1_first": ev["ai1_first"],
                            "winner": None,
                        }
                    if ev.get("type") == "move":
                        self.match_move_buffers[mid].append(
                            (ev["row"], ev["col"], ev["player"]))

                    # Auto-select a match to display if none selected
                    if self.display_match_id is None:
                        self.display_match_id = mid
                        self.display_moves = list(self.match_move_buffers.get(mid, []))

                    # If this is the currently displayed match, update immediately
                    if mid == self.display_match_id:
                        self.display_moves = list(self.match_move_buffers.get(mid, []))
                        self.move_count_var.set(f"Moves: {ev.get('move_num', len(self.display_moves))}")
                        self._update_display_label(mid)
                        self._redraw_board()

                        if ev.get("type") == "win":
                            self._log(f"  Match #{mid}: {ev['winner']} wins!")
            except QueueEmpty:
                pass

            # ----- Drain result queue -----
            try:
                while True:
                    result = self.result_queue.get_nowait()
                    self.match_results.append(result)
                    self.completed_count += 1
                    mid = result["match_id"]
                    self.active_match_ids.discard(mid)
                    self.completed_match_ids.add(mid)

                    # Store winner in match_meta (used by display label)
                    if mid in self.match_meta:
                        self.match_meta[mid]["winner"] = result["winner"]
                    else:
                        self.match_meta[mid] = {
                            "ai1_name": result["ai1_name"],
                            "ai2_name": result["ai2_name"],
                            "ai1_first": result["ai1_first"],
                            "winner": result["winner"],
                        }

                    self._update_stats(result)
                    self._log(
                        f"Match #{mid:03d}: {result['winner']} "
                        f"({result['moves']} moves, "
                        f"AI1:{result['ai1_time']:.2f}s AI2:{result['ai2_time']:.2f}s)"
                    )

                    # If the finished match was displayed, switch to a new one
                    if mid == self.display_match_id:
                        self.display_match_id = None
                        self.display_moves = []
                        self._pick_new_display_match()
            except QueueEmpty:
                pass

            # Check for unexpectedly terminated processes
            for i, p in enumerate(self.processes):
                if not p.is_alive() and p.exitcode != 0 and p.exitcode is not None:
                    self._log(f"  WARNING: Match process {i} exited with code {p.exitcode}")
                    self.active_match_ids.discard(i)

            # Check if all matches are done
            if self.completed_count >= self.match_count_var.get():
                self._finish_tournament()

        self.root.after(200, self._poll_queues)

    def _update_display_label(self, mid):
        """Set the match display label showing who plays which color and the winner.

        The label correctly assigns (●) to PLAYER=1 and (○) to AI=-1 based
        on who plays what side (determined by ai1_first):
        - ai1_first=True:  AI1 → AI → (○), AI2 → PLAYER → (●)
        - ai1_first=False: AI1 → PLAYER → (●), AI2 → AI → (○)
        """
        meta = self.match_meta.get(mid)
        if meta is None:
            self.display_match_label_str.set(f"Match {mid}")
            return
        n1 = meta["ai1_name"]
        n2 = meta["ai2_name"]
        if meta["ai1_first"]:
            # AI1 plays AI (-1, white ○), AI2 plays PLAYER (1, black ●)
            fn, sn = n2, n1
        else:
            # AI1 plays PLAYER (1, black ●), AI2 plays AI (-1, white ○)
            fn, sn = n1, n2
        base = f"Match {mid}: {fn}(●) vs {sn}(○)"
        if meta["winner"]:
            base += f" — {meta['winner']} wins!"
        status = " (done)" if mid in self.completed_match_ids else ""
        self.display_match_label_str.set(base + status)

    def _pick_new_display_match(self):
        """When the current match finishes, pick the next one to display.

        Iterates through candidates sorted by match_id (not random).
        """
        candidates = sorted(self.active_match_ids | self.completed_match_ids)
        if candidates:
            new_id = candidates[0]
            self.display_match_id = new_id
            self.display_moves = list(self.match_move_buffers.get(new_id, []))
            self.move_count_var.set(f"Moves: {len(self.display_moves)}")
            self._redraw_board()
            self._update_display_label(new_id)

    def _switch_display(self):
        """Switch the displayed match to the next one in sorted order.

        Cycles through candidates sequentially (not random), wrapping
        around at the end. Called by the "Switch Display" button.
        """
        candidates = sorted(self.active_match_ids | self.completed_match_ids)
        if not candidates:
            return
        if self.display_match_id is None:
            next_id = candidates[0]
        else:
            idx = candidates.index(self.display_match_id) + 1
            next_id = candidates[idx % len(candidates)]
        self.display_match_id = next_id
        self.display_moves = list(self.match_move_buffers.get(next_id, []))
        self.move_count_var.set(f"Moves: {len(self.display_moves)}")
        self._redraw_board()
        self._update_display_label(next_id)
        meta = self.match_meta.get(next_id, {})
        winner = meta.get("winner", "?")
        self._log(f"Switched display to match {next_id} — {winner}")

    def _update_stats(self, _result=None):
        """Recalculate and update all statistics displayed in the stats panel.

        Computes:
        - Win counts and win rates for both AIs
        - Average move times (accounting for who moved how many times)
        - Draw count

        Called after each match result is received.
        """
        ai1_name = self._read_ai_config(1)[0]["name"]
        ai2_name = self._read_ai_config(2)[0]["name"]

        ai1_wins = sum(1 for r in self.match_results if r["winner"] == ai1_name)
        ai2_wins = sum(1 for r in self.match_results if r["winner"] == ai2_name)
        draws = sum(1 for r in self.match_results if r["winner"] == "draw")

        ai1_total = sum(r["ai1_time"] for r in self.match_results)
        ai2_total = sum(r["ai2_time"] for r in self.match_results)
        ai1_moves = sum(r["moves"] // 2 for r in self.match_results if r["ai1_first"])
        ai1_moves += sum(r["moves"] - r["moves"] // 2 for r in self.match_results if not r["ai1_first"])
        ai2_moves = sum(r["moves"] - r["moves"] // 2 for r in self.match_results if r["ai1_first"])
        ai2_moves += sum(r["moves"] // 2 for r in self.match_results if not r["ai1_first"])

        ai1_avg = ai1_total / max(ai1_moves, 1)
        ai2_avg = ai2_total / max(ai2_moves, 1)
        total_decided = ai1_wins + ai2_wins
        ai1_wr = f"{ai1_wins / max(total_decided, 1) * 100:.1f}%"
        ai2_wr = f"{ai2_wins / max(total_decided, 1) * 100:.1f}%"

        self.stats_vars["completed"].set(str(self.completed_count))
        self.stats_vars["ai1_wins"].set(str(ai1_wins))
        self.stats_vars["ai2_wins"].set(str(ai2_wins))
        self.stats_vars["draws"].set(str(draws))
        self.stats_vars["ai1_avg_time"].set(f"{ai1_avg:.3f}s")
        self.stats_vars["ai2_avg_time"].set(f"{ai2_avg:.3f}s")
        self.stats_vars["ai1_winrate"].set(ai1_wr)
        self.stats_vars["ai2_winrate"].set(ai2_wr)

    # ===================== REPLAY =====================

    def _start_replay(self):
        """Begin replaying the currently displayed match move by move.

        Resets the display to an empty board, then steps through
        the move buffer at the configured speed.
        """
        if self.display_match_id is None:
            return
        if self.display_match_id not in self.match_move_buffers:
            self._log("No moves for current match to replay")
            return
        self.replay_active = True
        self.replay_paused = False
        self.replay_index = 0
        self.display_moves = []
        self._redraw_board()
        self.pause_btn.configure(text="Pause")
        self._log(f"Replaying match {self.display_match_id}...")
        self._run_replay_step()

    def _toggle_pause_replay(self):
        """Toggle the replay pause state."""
        self.replay_paused = not self.replay_paused
        self.pause_btn.configure(text="Resume" if self.replay_paused else "Pause")
        if not self.replay_paused and self.replay_active:
            self._run_replay_step()

    def _run_replay_step(self):
        """Execute one step of the replay: show one more move.

        Called by root.after() with a delay of replay_speed * 1000 ms.
        When all moves have been shown, stops the replay.
        """
        if not self.replay_active or self.replay_paused:
            return
        buffer = self.match_move_buffers.get(self.display_match_id, [])
        if self.replay_index >= len(buffer):
            self.replay_active = False
            self.pause_btn.configure(text="Pause")
            self._log("Replay finished.")
            return
        # Show moves up to current index
        self.display_moves = buffer[:self.replay_index + 1]
        self.move_count_var.set(f"Moves: {len(self.display_moves)}")
        self._redraw_board()
        self.replay_index += 1
        ms = int(self.replay_speed.get() * 1000)
        self.root.after(ms, self._run_replay_step)

    # ===================== TOURNAMENT END =====================

    def _finish_tournament(self):
        """Called when all matches complete. Updates UI and writes summary.

        Re-enables all control buttons and logs final results including
        win rates and any subprocess errors.
        """
        self.running = False
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.switch_btn.configure(state=tk.NORMAL)
        self.replay_btn.configure(state=tk.NORMAL)
        self.replay_slider.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.NORMAL)

        ai1_name = self._read_ai_config(1)[0]["name"]
        ai2_name = self._read_ai_config(2)[0]["name"]
        ai1_wins = sum(1 for r in self.match_results if r["winner"] == ai1_name)
        ai2_wins = sum(1 for r in self.match_results if r["winner"] == ai2_name)
        draws = sum(1 for r in self.match_results if r["winner"] == "draw")

        self._log("=" * 50)
        self._log(f"TOURNAMENT COMPLETE — {self.completed_count} matches")
        self._log(f"  {ai1_name}: {ai1_wins} wins "
                  f"({ai1_wins / max(self.completed_count, 1) * 100:.1f}%)")
        self._log(f"  {ai2_name}: {ai2_wins} wins "
                  f"({ai2_wins / max(self.completed_count, 1) * 100:.1f}%)")
        self._log(f"  Draws: {draws}")
        self._log("=" * 50)

        # Check error log for subprocess crashes
        try:
            if self.error_file.exists() and self.error_file.stat().st_size > 0:
                self._log(f"  *** ERRORS FOUND in {self.error_file} ***")
                for line in self.error_file.read_text().splitlines()[-10:]:
                    self._log(f"  {line}")
        except Exception:
            pass

        self._write_summary()

    def _write_summary(self):
        """Write aggregated tournament results to summary.json.

        Includes full configs, win counts, timing, and all match data.
        Written to simulation/logs/{session_ts}/summary.json.
        """
        ai1_cfg_dict, _, _ = self._read_ai_config(1)
        ai2_cfg_dict, _, _ = self._read_ai_config(2)
        ai1_name = ai1_cfg_dict["name"]
        ai2_name = ai2_cfg_dict["name"]
        ai1_wins = sum(1 for r in self.match_results if r["winner"] == ai1_name)
        ai2_wins = sum(1 for r in self.match_results if r["winner"] == ai2_name)
        draws = sum(1 for r in self.match_results if r["winner"] == "draw")

        summary = {
            "timestamp": self.session_ts,
            "total_matches": self.completed_count,
            "ai1": {
                "name": ai1_name,
                "config": ai1_cfg_dict,
                "wins": ai1_wins,
                "win_rate": round(ai1_wins / max(self.completed_count, 1), 4),
                "avg_time_per_move": self.stats_vars["ai1_avg_time"].get(),
            },
            "ai2": {
                "name": ai2_name,
                "config": ai2_cfg_dict,
                "wins": ai2_wins,
                "win_rate": round(ai2_wins / max(self.completed_count, 1), 4),
                "avg_time_per_move": self.stats_vars["ai2_avg_time"].get(),
            },
            "draws": draws,
            "matches": self.match_results,
        }

        try:
            summary_path = self.log_dir / "summary.json"
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2, default=str)
            self._log(f"Summary written to {summary_path}")
        except Exception as e:
            self._log(f"Error writing summary: {e}")

    def _log(self, message):
        """Append a timestamped message to the log panel."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {message}\n")
        self.log_text.see(tk.END)

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Use spawn start method for multiprocessing (required for macOS, works on Linux)
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass  # already set

    app = SimulationGUI()
    app.run()


if __name__ == "__main__":
    main()
