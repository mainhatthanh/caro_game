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
    if idx < 0 or idx >= len(line):
        return "#"

    cell = line[idx]
    if cell == EMPTY:
        return "."
    if cell == player:
        return None
    return "E"


def evaluate_line_for_player(line, player):
    n = len(line)
    score = 0
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

    for start, length in runs:
        left = _run_side(line, start - 1, player)
        right = _run_side(line, start + length, player)

        both_open = left == "." and right == "."
        one_open = (left == ".") != (right == ".")

        if length >= 5:
            if left != "E" and right != "E" and (left == "." or right == "."):
                score += PATTERN_SCORES["FIVE"]
        elif length == 4:
            if both_open:
                score += PATTERN_SCORES["OPEN_FOUR"]
            elif one_open:
                score += PATTERN_SCORES["SEMI_OPEN_FOUR"]
        elif length == 3:
            if both_open:
                score += PATTERN_SCORES["OPEN_THREE"]
            elif one_open:
                score += PATTERN_SCORES["SEMI_OPEN_THREE"]
        elif length == 2:
            if both_open:
                score += PATTERN_SCORES["OPEN_TWO"]
            elif one_open:
                score += PATTERN_SCORES["SEMI_OPEN_TWO"]
        elif length == 1 and both_open:
            score += PATTERN_SCORES["OPEN_ONE"]

    for run_idx in range(len(runs) - 1):
        start1, len1 = runs[run_idx]
        start2, len2 = runs[run_idx + 1]
        gap = start2 - (start1 + len1)

        if gap != 1 or line[start1 + len1] != EMPTY:
            continue

        total = len1 + len2
        left = _run_side(line, start1 - 1, player)
        right = _run_side(line, start2 + len2, player)

        both_open = left == "." and right == "."
        one_open = (left == ".") != (right == ".")

        if total == 4:
            if both_open:
                score += PATTERN_SCORES["BROKEN_FOUR"]
            elif one_open:
                score += PATTERN_SCORES["SEMI_BROKEN_FOUR"]
        elif total == 3:
            if both_open:
                score += PATTERN_SCORES["BROKEN_THREE"]
            elif one_open:
                score += PATTERN_SCORES["SEMI_OPEN_THREE"]
        elif total == 2:
            if both_open:
                score += PATTERN_SCORES["BROKEN_TWO"]
            elif one_open:
                score += PATTERN_SCORES["SEMI_OPEN_TWO"]

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
