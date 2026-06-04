"""Board evaluation — run-length pattern scoring for the Caro AI.

The evaluation function uses run-length analysis on all 4 directions
(horizontal, vertical, 2 diagonals). For each direction, it extracts
contiguous lines of cells and scores them by:

1. Single runs — contiguous stones of the same player
2. Broken patterns — two runs separated by exactly 1 empty cell
   (gap patterns like .MM.M. are scored as BROKEN_THREE)

The final board score is:
    ai_score - 1.5 * player_score

The 1.5x multiplier makes the AI defend more aggressively than it attacks.
"""

from constants import (
    BOARD_SIZE, EMPTY, PLAYER, AI, PATTERN_SCORES,
    THREAT_NONE, THREAT_FIVE, THREAT_OPEN_FOUR, THREAT_SEMI_OPEN_FOUR,
    THREAT_OPEN_THREE, THREAT_SEMI_OPEN_THREE, THREAT_OPEN_TWO,
)


# ---------------------------------------------------------------------------
# Line extraction — slice the board into 1D lines for each direction
# ---------------------------------------------------------------------------

def get_all_lines(board):
    """Extract all 1D lines from the board in 4 directions.

    Returns a flat list of line segments (as lists of cell values).
    Only returns segments of length >= 5 (shorter segments can't contain
    a winning line, though they can contain shorter patterns that contribute
    to the positional score).

    Lines returned: BOARD_SIZE horizontals + BOARD_SIZE verticals +
    (2*BOARD_SIZE - 1) diagonals ↘ + (2*BOARD_SIZE - 1) anti-diagonals ↙
    """
    lines = []

    # 1. Horizontal rows
    for row in range(BOARD_SIZE):
        lines.append([board[row][col] for col in range(BOARD_SIZE)])

    # 2. Vertical columns
    for col in range(BOARD_SIZE):
        lines.append([board[row][col] for row in range(BOARD_SIZE)])

    # 3. Main diagonal ↘ (top-left to bottom-right)
    for start_col in range(BOARD_SIZE):
        line = []
        row, col = 0, start_col
        while row < BOARD_SIZE and col < BOARD_SIZE:
            line.append(board[row][col])
            row += 1
            col += 1
        if len(line) >= 5:
            lines.append(line)

    for start_row in range(1, BOARD_SIZE):
        line = []
        row, col = start_row, 0
        while row < BOARD_SIZE and col < BOARD_SIZE:
            line.append(board[row][col])
            row += 1
            col += 1
        if len(line) >= 5:
            lines.append(line)

    # 4. Anti diagonal ↙ (top-right to bottom-left)
    for start_col in range(BOARD_SIZE):
        line = []
        row, col = 0, start_col
        while row < BOARD_SIZE and col >= 0:
            line.append(board[row][col])
            row += 1
            col -= 1
        if len(line) >= 5:
            lines.append(line)

    for start_row in range(1, BOARD_SIZE):
        line = []
        row, col = start_row, BOARD_SIZE - 1
        while row < BOARD_SIZE and col >= 0:
            line.append(board[row][col])
            row += 1
            col -= 1
        if len(line) >= 5:
            lines.append(line)

    return lines


def _run_side(line, idx, player):
    """Return the character representing the cell at `idx` in `line`.

    '.' = EMPTY (open end)
    'E' = opponent stone (blocked end)
    '#' = wall (board edge — treated as blocked)
    None = part of the same run (shouldn't happen when called correctly)
    """
    if idx < 0 or idx >= len(line):
        return '#'
    cell = line[idx]
    if cell == EMPTY:
        return '.'
    if cell == player:
        return None  # part of the run, shouldn't happen
    return 'E'


# ---------------------------------------------------------------------------
# Single line evaluation — the core scoring function
# ---------------------------------------------------------------------------

def evaluate_line_for_player(line, player):
    """Score a single line for `player` using run-length analysis.

    Replaced the old 49-pattern string matching with O(n) scan.

    Phase 1: Find all contiguous runs of player stones
    Phase 2: Score each run by length and open-end status
    Phase 3: Score broken patterns (2 runs separated by exactly 1 empty cell)

    A "broken" pattern like .MM.M. is dangerous because filling the gap
    creates an open-four, so it scores similarly to a solid run of the
    same total length.
    """
    n = len(line)
    score = 0

    # ----- Phase 1: find all runs of player stones -----
    runs = []
    i = 0
    while i < n:
        if line[i] == player:
            start = i
            while i < n and line[i] == player:
                i += 1
            runs.append((start, i - start))
        else:
            i += 1

    if not runs:
        return 0

    # ----- Phase 2: score single runs -----
    for start, length in runs:
        left = _run_side(line, start - 1, player)
        right = _run_side(line, start + length, player)

        both_open = (left == '.' and right == '.')
        one_open = (left == '.') != (right == '.')

        if length >= 5:
            # FIVE must have at least one open end.
            # board-wall-board (both '#') means no extension possible = 0.
            if left != 'E' and right != 'E' and (left == '.' or right == '.'):
                score += PATTERN_SCORES["FIVE"]
        elif length == 4:
            if both_open:          score += PATTERN_SCORES["OPEN_FOUR"]
            elif one_open:         score += PATTERN_SCORES["SEMI_OPEN_FOUR"]
        elif length == 3:
            if both_open:          score += PATTERN_SCORES["OPEN_THREE"]
            elif one_open:         score += PATTERN_SCORES["SEMI_OPEN_THREE"]
        elif length == 2:
            if both_open:          score += PATTERN_SCORES["OPEN_TWO"]
            elif one_open:         score += PATTERN_SCORES["SEMI_OPEN_TWO"]
        elif length == 1:
            if both_open:          score += PATTERN_SCORES["OPEN_ONE"]

    # ----- Phase 3: broken patterns (gap of exactly 1) -----
    for ri in range(len(runs) - 1):
        start1, len1 = runs[ri]
        start2, len2 = runs[ri + 1]
        gap = start2 - (start1 + len1)

        if gap != 1:
            continue
        if line[start1 + len1] != EMPTY:
            continue

        total = len1 + len2

        left = _run_side(line, start1 - 1, player)
        right = _run_side(line, start2 + len2, player)

        both_open = (left == '.' and right == '.')
        one_open = (left == '.') != (right == '.')

        if total == 4:
            if both_open:          score += PATTERN_SCORES["BROKEN_FOUR"]
            elif one_open:         score += PATTERN_SCORES["SEMI_BROKEN_FOUR"]
        elif total == 3:
            if both_open:          score += PATTERN_SCORES["BROKEN_THREE"]
            elif one_open:         score += PATTERN_SCORES["SEMI_OPEN_THREE"]
        elif total == 2:
            if both_open:          score += PATTERN_SCORES["BROKEN_TWO"]
            elif one_open:         score += PATTERN_SCORES["SEMI_OPEN_TWO"]

    return score


# ---------------------------------------------------------------------------
# Full board evaluation
# ---------------------------------------------------------------------------

def evaluate_player(board, player):
    """Sum the evaluation score for `player` across all lines on the board."""
    total = 0
    lines = get_all_lines(board)

    for line in lines:
        total += evaluate_line_for_player(line, player)

    return total


def evaluate_board(board):
    """Evaluate the full board from AI's perspective.

    Formula: ai_score - 1.5 * player_score

    The 1.5x multiplier is intentional:
    - AI plays more aggressively on defense (blocks opponent threats sooner)
    - Without it, the AI can be too "optimistic" about its own position
    - The asymmetry reflects that opponent threats need ~50% more weight
      to account for the fact that opponent plays next in alternating search
    """
    ai_score = evaluate_player(board, AI)
    player_score = evaluate_player(board, PLAYER)

    return ai_score - 1.5 * player_score


# ---------------------------------------------------------------------------
# Per-cell evaluation — used during search for move delta computation
# ---------------------------------------------------------------------------

DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1)]


def get_lines_through(board, row, col, extend=5):
    """Return the 4 line segments passing through (row, col).

    Each segment is extended `extend` cells in both directions from
    (row, col), clamped to board bounds.

    Returns a list of (segment, stone_idx) tuples, where stone_idx is
    the position of the (row, col) cell within the segment.
    Segments shorter than 5 cells are filtered out.
    """
    lines = []
    for dr, dc in DIRECTIONS:
        segment = []
        # Backward from (row, col) — prepend cells
        r, c = row - dr, col - dc
        for _ in range(extend):
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                segment.insert(0, board[r][c])
            r -= dr
            c -= dc
        stone_idx = len(segment)  # the stone goes right after backward cells
        # The cell itself
        segment.append(board[row][col])
        # Forward from (row, col) — append cells
        r, c = row + dr, col + dc
        for _ in range(extend):
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                segment.append(board[r][c])
            r += dr
            c += dc
        if len(segment) >= 5:
            lines.append((segment, stone_idx))
    return lines


def classify_axis_threat(segment, stone_idx, player):
    """Classify the threat level on ONE axis (one line segment) through a placed stone.

    This is similar to classify_axis() in ai.py, but operates on pre-extracted
    segments rather than the raw board. Used by the pre-search pipeline's
    find_single_axis_threat() to evaluate candidate moves.

    Scans both directions from stone_idx, counts contiguous stones of `player`,
    checks open ends, and returns a THREAT_* constant.

    NOTE: This only handles single-axis threats (one direction). Compound
    threats (forks) are detected by detect_fork() which combines results
    from all 4 axes.
    """
    n = len(segment)
    # Count contiguous stones to the left and right of the placed cell
    left_count = 0
    i = stone_idx - 1
    while i >= 0 and segment[i] == player:
        left_count += 1
        i -= 1
    left_open = i >= 0 and segment[i] == EMPTY

    right_count = 0
    i = stone_idx + 1
    while i < n and segment[i] == player:
        right_count += 1
        i += 1
    right_open = i < n and segment[i] == EMPTY

    total = left_count + 1 + right_count  # including the stone itself

    if total >= 5:
        return THREAT_FIVE

    if total == 4:
        if left_open and right_open:
            return THREAT_OPEN_FOUR
        elif left_open or right_open:
            return THREAT_SEMI_OPEN_FOUR
        return THREAT_NONE  # dead four — both ends blocked

    if total == 3:
        if left_open and right_open:
            return THREAT_OPEN_THREE
        elif left_open or right_open:
            return THREAT_SEMI_OPEN_THREE
        return THREAT_NONE

    if total == 2:
        if left_open and right_open:
            return THREAT_OPEN_TWO
        return THREAT_NONE

    return THREAT_NONE


def evaluate_position_score(board, row, col):
    """Evaluate score contribution of the 4 lines through (row, col).

    Computes ai_score - 1.5 * player_score for just the lines intersecting
    this cell. Used for incremental evaluation during search (though the
    current implementation recomputes from scratch rather than delta).
    """
    lines = get_lines_through(board, row, col)
    total = 0
    for segment, _stone_idx in lines:
        total += evaluate_line_for_player(segment, AI)
        total -= 1.5 * evaluate_line_for_player(segment, PLAYER)
    return total


def compute_move_delta(board, row, col, player):
    """Compute the change in board evaluation if `player` is placed at (row, col).

    Does NOT modify the board. Instead:
    1. For each of the 4 lines through (row, col):
       a. Evaluate the line for both AI and PLAYER (the "before" state)
       b. Temporarily place `player` at the cell
       c. Re-evaluate both sides (the "after" state)
       d. Restore the cell
    2. Sum the deltas across all 4 axes

    Only lines through (row, col) are affected by a single stone placement,
    so we only need to evaluate those 4 lines, not the full board.
    This is a significant optimization during search.
    """
    lines = get_lines_through(board, row, col)
    delta = 0
    for segment, stone_idx in lines:
        # Before: player has '.' at position, opponent has '.' at position
        old_ai = evaluate_line_for_player(segment, AI)
        old_player = evaluate_line_for_player(segment, PLAYER)
        # Temporarily place the stone for "after" evaluation
        saved = segment[stone_idx]
        segment[stone_idx] = player
        new_ai = evaluate_line_for_player(segment, AI)
        new_player = evaluate_line_for_player(segment, PLAYER)
        segment[stone_idx] = saved
        delta += (new_ai - old_ai) - 1.5 * (new_player - old_player)
    return delta
