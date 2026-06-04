"""Console-based Caro game — player vs AI in the terminal.

The player plays as X, the AI plays as O. Game alternates turns:
1. Player enters row and column
2. Board is displayed
3. AI responds
4. Board is displayed
5. Repeat until win or draw

Difficulty maps to AI search depth:
- Easy = depth 1 (very weak, basically random)
- Medium = depth 2
- Hard = depth 3-5 (with iterative deepening)
"""

from constants import PLAYER, AI
from board import create_board, print_board, make_move, get_player_move
from rules import check_winner, is_board_full
from ai import ai_move


def main():
    board = create_board()
    level = int(input("Vui lòng nhập độ khó muốn chơi (1-2-3): "))

    while True:
        # ----- Player's turn -----
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

        # ----- AI's turn -----
        ai_move_pos = ai_move(board, level)
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
