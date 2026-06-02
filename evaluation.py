from constants import BOARD_SIZE, EMPTY, PLAYER, AI, PATTERN_SCORES


def get_all_lines(board):
    lines = []

    # 1. Hàng ngang
    for row in range(BOARD_SIZE):
        lines.append([board[row][col] for col in range(BOARD_SIZE)])

    # 2. Cột dọc
    for col in range(BOARD_SIZE):
        lines.append([board[row][col] for row in range(BOARD_SIZE)])

    # 3. Chéo xuống phải
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

    # 4. Chéo xuống trái
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
    """Return '.' for EMPTY, 'E' for opponent, '#' for wall."""
    if idx < 0 or idx >= len(line):
        return '#'
    cell = line[idx]
    if cell == EMPTY:
        return '.'
    if cell == player:
        return None  # part of the run, shouldn't happen
    return 'E'


def evaluate_line_for_player(line, player):
    """Score a single line using run-length analysis.
    Replaces the old 49-pattern string matching with O(len(line)) scan."""
    n = len(line)
    score = 0

    # Phase 1: find all runs of player stones
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

    # Phase 2: score single runs
    for start, length in runs:
        left = _run_side(line, start - 1, player)
        right = _run_side(line, start + length, player)

        both_open = (left == '.' and right == '.')
        one_open = (left == '.') != (right == '.')

        if length >= 5:
            # Only score FIVE when at least one side is open
            # (having 5+ blocked on both sides means wall-wall = 0 FIVE)
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

    # Phase 3: broken patterns (2 runs separated by exactly 1 empty cell)
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


def evaluate_player(board, player):
    total = 0
    lines = get_all_lines(board)

    for line in lines:
        total += evaluate_line_for_player(line, player)

    return total


def evaluate_board(board):
    ai_score = evaluate_player(board, AI)
    player_score = evaluate_player(board, PLAYER)

    return ai_score - 1.5 * player_score

DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1)]

def get_lines_through(board, row, col, extend=5):
    """Return the 4 line segments passing through (row, col), each extended
    `extend` cells in both directions (clamped to board bounds).
    The cell at (row, col) is included at its current value.
    Returns list of (segment, stone_idx) tuples — stone_idx is the position
    of the (row, col) stone within the segment."""
    lines = []
    for dr, dc in DIRECTIONS:
        segment = []
        # Backward from (row, col)
        r, c = row - dr, col - dc
        for _ in range(extend):
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                segment.insert(0, board[r][c])
            r -= dr
            c -= dc
        stone_idx = len(segment)  # the stone goes right after backward cells
        # The cell itself
        segment.append(board[row][col])
        # Forward from (row, col)
        r, c = row + dr, col + dc
        for _ in range(extend):
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                segment.append(board[r][c])
            r += dr
            c += dc
        if len(segment) >= 5:
            lines.append((segment, stone_idx))
    return lines


def evaluate_position_score(board, row, col):
    """Evaluate the contribution of the 4 lines through (row, col) to the total
    board score (ai_score - 1.5 * player_score)."""
    lines = get_lines_through(board, row, col)
    total = 0
    for segment, _stone_idx in lines:
        total += evaluate_line_for_player(segment, AI)
        total -= 1.5 * evaluate_line_for_player(segment, PLAYER)
    return total


def compute_move_delta(board, row, col, player):
    """Compute the change in total board score if `player` is placed at (row, col).
    Does NOT modify the board.
    Only evaluates the 4 lines through (row, col) once each, for both players,
    avoiding double evaluation."""
    lines = get_lines_through(board, row, col)
    delta = 0
    for segment, stone_idx in lines:
        # Before: player has '.' at position (blocked), opponent has '.' at position
        # After:  player has 'M' at position, opponent has 'E' at position
        # Recompute for BOTH and subtract old, all in one pass
        old_ai = evaluate_line_for_player(segment, AI)
        old_player = evaluate_line_for_player(segment, PLAYER)
        # Temporarily place the stone for new eval
        saved = segment[stone_idx]
        segment[stone_idx] = player
        new_ai = evaluate_line_for_player(segment, AI)
        new_player = evaluate_line_for_player(segment, PLAYER)
        segment[stone_idx] = saved
        delta += (new_ai - old_ai) - 1.5 * (new_player - old_player)
    return delta