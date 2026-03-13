import random
BOARD_SIZE = 15

EMPTY = 0
PLAYER = 1
AI = - 1

PATTERN_SCORES = {
    # 5 quân
    "FIVE": 1000000,

    # 4 mạnh
    "OPEN_FOUR": 120000,         
    "SEMI_OPEN_FOUR": 15000,     
    "BROKEN_FOUR": 18000,        
    "SEMI_BROKEN_FOUR": 6000,

    # 3 mạnh
    "OPEN_THREE": 5000,          
    "BROKEN_THREE": 3500,        
    "SEMI_OPEN_THREE": 800,

    # 2
    "OPEN_TWO": 300,            
    "BROKEN_TWO": 150,          
    "SEMI_OPEN_TWO": 50,

    # 1
    "OPEN_ONE": 10
}
def create_board():
    return [[EMPTY for _ in range(BOARD_SIZE)] for _ in range (BOARD_SIZE)]

def print_board(board):
    #In số cột
    print(" ", end = "")
    for col in range(BOARD_SIZE):
        print(f"{col}", end = "")
    print()

    for row in range(BOARD_SIZE):
        print(f"{row:2}", end = "")
        for col in range(BOARD_SIZE):
            if board[row][col] == PLAYER:
                symbol = "X"
            elif board[row][col] == AI:
                symbol = "0"
            else:
                symbol = "."
            print(f"{symbol}", end = "")
        print()

def make_move(board, row, col, player):
    if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
        if board[row][col] == EMPTY:
            board[row][col] = player
            return True
        return False
    
def get_player_move():
    while True:
        try:
            row = int(input("Nhap hang (0 - 14): "))
            col = int(input("Nhap cot (0 - 14): "))
            return row, col
        except ValueError:
            print("Vui long nhap so nguyen")

def check_five_from_cell(board, row, col, player):
    directions = [
        (0, 1), #ngang
        (1, 0), #dọc
        (1, 1), #chéo xuống phải
        (1, -1), #chéo xuống trái
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
            #Ô trước đầu chuỗi
            prev_r = row - dr
            prev_c = col - dc

            #Ô sau cuối chuỗi
            next_r = row + dr*5
            next_c = col + dc*5

            prev_blocked = False
            next_blocked = False

            if 0 <= prev_r < BOARD_SIZE and 0 <= prev_c < BOARD_SIZE:
                if board[prev_r][prev_c] == opponent:
                    prev_blocked = True

            if 0 <= next_r < BOARD_SIZE and 0 <= next_c < BOARD_SIZE:
                if board[next_r][next_c] == opponent:
                    next_blocked = True

            #Nếu cả hai đầu đều bị chặn thì không thắng
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

def get_empty_cells(board):
    empty_cells = []

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY:
                empty_cells.append((row, col))
    return empty_cells


def has_neighbor(board, row, col, distance = 1):
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

def get_candidate_moves(board, distance = 1):
    candidates_moves = []

    #Kiểm tra bàn cờ có trống không
    is_empty_board = True
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] != EMPTY:
                is_empty_board = False
                break
        if not is_empty_board:
            break

    #Nếu bàn trống thì ưu tiên đánh giữa
    if is_empty_board:
        center = BOARD_SIZE // 2
        return [(center, center)]
    
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] == EMPTY and has_neighbor(board, row, col, distance):
                candidates_moves.append((row, col))

    return candidates_moves


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

    #1. Hàng ngang
    for row in range(BOARD_SIZE):
        lines.append([board[row][col] for col in range(BOARD_SIZE)])

    #2. Cột dọc
    for col in range(BOARD_SIZE):
        lines.append([board[row][col] for row in range(BOARD_SIZE)])

    #3. Chéo xuống dưới phải
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
    
     # 4. Chéo xuống dưới trái
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

    # ===== FIVE =====
    # Thắng thật sự chỉ nên do check_winner quyết định.
    # Ở heuristic, vẫn chấm cực lớn cho 5 không bị chặn hai đầu.
    score += count_overlapping(s, ".MMMMM.") * PATTERN_SCORES["FIVE"]
    score += count_overlapping(s, "#MMMMM.") * PATTERN_SCORES["FIVE"]
    score += count_overlapping(s, ".MMMMM#") * PATTERN_SCORES["FIVE"]

    # Nếu là #MMMMM# thì theo luật của bạn bị chặn 2 đầu => chưa thắng
    # Không cộng điểm hoặc cộng rất thấp
    # score += count_overlapping(s, "#MMMMM#") * 0

    # ===== OPEN FOUR =====
    score += count_overlapping(s, ".MMMM.") * PATTERN_SCORES["OPEN_FOUR"]

    # ===== SEMI OPEN FOUR =====
    score += count_overlapping(s, "EMMMM.") * PATTERN_SCORES["SEMI_OPEN_FOUR"]
    score += count_overlapping(s, ".MMMME") * PATTERN_SCORES["SEMI_OPEN_FOUR"]
    score += count_overlapping(s, "#MMMM.") * PATTERN_SCORES["SEMI_OPEN_FOUR"]
    score += count_overlapping(s, ".MMMM#") * PATTERN_SCORES["SEMI_OPEN_FOUR"]

    # ===== BROKEN FOUR =====
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

    # ===== OPEN THREE =====
    score += count_overlapping(s, ".MMM.") * PATTERN_SCORES["OPEN_THREE"]

    # ===== BROKEN THREE =====
    broken_three_patterns = [
        ".MM.M.",
        ".M.MM."
    ]
    for p in broken_three_patterns:
        score += count_overlapping(s, p) * PATTERN_SCORES["BROKEN_THREE"]

    # ===== SEMI OPEN THREE =====
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

    # ===== OPEN TWO =====
    score += count_overlapping(s, ".MM.") * PATTERN_SCORES["OPEN_TWO"]

    # ===== BROKEN TWO =====
    score += count_overlapping(s, ".M.M.") * PATTERN_SCORES["BROKEN_TWO"]

    # ===== SEMI OPEN TWO =====
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

    # ===== OPEN ONE =====
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

    return ai_score - player_score


def find_best_move_by_heuristic(board):
    candidate_moves = get_candidate_moves(board, distance = 1)

    if not candidate_moves:
        return None
    
    best_score = float("-inf")
    best_moves = []

    for row, col in candidate_moves:
        #Thử đánh
        board[row][col] = AI

        #Chấm điểm bàn cờ cho nước đi này
        score = evaluate_board(board)

        #Hoàn tác
        board[row][col] = EMPTY

        if score > best_score:
            best_score = score
            best_moves = [(row, col)]
        elif score == best_score:
            best_moves.append((row, col))

    return random.choice(best_moves)

# def ai_random_move(board):
#     candidate_moves= get_candidate_moves(board, distance=1)
#     if not candidate_moves:
#         return None

#     return random.choice(candidate_moves)

def ai_move(board):
    return find_best_move_by_heuristic(board)


def main():
    board = create_board()

    while True:
        #Lượt người chơi 
        print_board(board)
        row, col = get_player_move()

        if not make_move(board, row, col, PLAYER):
            print("Nước đi không hợp lệ. Hãy chọn ô trống trong phạm vi 0-14.")
            continue

        print(f"Bạn đã đánh X tại vị trí: ({row}, {col})")

        if check_winner(board, PLAYER):
            print_board(board)
            print("Chúc mừng! Bạn đã thắng.")
            break

        if is_board_full(board):
            print_board(board)
            print("Bàn cờ đã đầy. Kết quả hòa.")
            break

        #Lượt máy 
        ai_move_pos = ai_move(board)
        if ai_move_pos is None:
            print_board(board)
            print("Bàn cờ đã đầy. Kết quả hòa.")
            break

        ai_row, ai_col = ai_move_pos
        make_move(board, ai_row, ai_col, AI)
        print(f"Máy đã đánh O tại vị trí: ({ai_row}, {ai_col})")

        if check_winner(board, AI):
            print_board(board)
            print("Máy đã thắng.")
            break

        if is_board_full(board):
            print_board(board)
            print("Bàn cờ đã đầy. Kết quả hòa.")
            break
    


if __name__ == "__main__":
    main()