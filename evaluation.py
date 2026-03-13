from constants import BOARD_SIZE, EMPTY, PLAYER, AI, PATTERN_SCORES


def count_overlapping(line, pattern):
    count = 0
    start = 0

    while True:
        idx = line.find(pattern, start)
        if idx == -1:
            break
        count += 1
        start = idx + 1

    return count


def normalize_line(line, player):
    chars = ["#"]

    for cell in line:
        if cell == EMPTY:
            chars.append(".")
        elif cell == player:
            chars.append("M")
        else:
            chars.append("E")

    chars.append("#")
    return "".join(chars)


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


def evaluate_line_for_player(line, player):
    s = normalize_line(line, player)
    score = 0

    score += count_overlapping(s, ".MMMMM.") * PATTERN_SCORES["FIVE"]
    score += count_overlapping(s, "#MMMMM.") * PATTERN_SCORES["FIVE"]
    score += count_overlapping(s, ".MMMMM#") * PATTERN_SCORES["FIVE"]

    score += count_overlapping(s, ".MMMM.") * PATTERN_SCORES["OPEN_FOUR"]

    score += count_overlapping(s, "EMMMM.") * PATTERN_SCORES["SEMI_OPEN_FOUR"]
    score += count_overlapping(s, ".MMMME") * PATTERN_SCORES["SEMI_OPEN_FOUR"]
    score += count_overlapping(s, "#MMMM.") * PATTERN_SCORES["SEMI_OPEN_FOUR"]
    score += count_overlapping(s, ".MMMM#") * PATTERN_SCORES["SEMI_OPEN_FOUR"]

    broken_four_patterns = [
        ".MMM.M.",
        ".MM.MM.",
        ".M.MMM."
    ]
    for p in broken_four_patterns:
        score += count_overlapping(s, p) * PATTERN_SCORES["BROKEN_FOUR"]

    semi_broken_four_patterns = [
        "EMMM.M.",
        ".MMM.ME",
        "EMM.MM.",
        ".MM.MME",
        "EM.MMM.",
        ".M.MMME",
        "#MMM.M.",
        ".MMM.M#",
        "#MM.MM.",
        ".MM.MM#",
        "#M.MMM.",
        ".M.MMM#"
    ]
    for p in semi_broken_four_patterns:
        score += count_overlapping(s, p) * PATTERN_SCORES["SEMI_BROKEN_FOUR"]

    score += count_overlapping(s, ".MMM.") * PATTERN_SCORES["OPEN_THREE"]

    broken_three_patterns = [
        ".MM.M.",
        ".M.MM."
    ]
    for p in broken_three_patterns:
        score += count_overlapping(s, p) * PATTERN_SCORES["BROKEN_THREE"]

    semi_open_three_patterns = [
        "EMMM.",
        ".MMME",
        "#MMM.",
        ".MMM#",
        "EMM.M.",
        ".MM.ME",
        "EM.MM.",
        ".M.MME",
        "#MM.M.",
        ".MM.M#",
        "#M.MM.",
        ".M.MM#"
    ]
    for p in semi_open_three_patterns:
        score += count_overlapping(s, p) * PATTERN_SCORES["SEMI_OPEN_THREE"]

    score += count_overlapping(s, ".MM.") * PATTERN_SCORES["OPEN_TWO"]

    score += count_overlapping(s, ".M.M.") * PATTERN_SCORES["BROKEN_TWO"]

    semi_open_two_patterns = [
        "EMM.",
        ".MME",
        "#MM.",
        ".MM#",
        "EM.M.",
        ".M.ME",
        "#M.M.",
        ".M.M#"
    ]
    for p in semi_open_two_patterns:
        score += count_overlapping(s, p) * PATTERN_SCORES["SEMI_OPEN_TWO"]

    score += count_overlapping(s, ".M.") * PATTERN_SCORES["OPEN_ONE"]

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