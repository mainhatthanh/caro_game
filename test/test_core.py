import io
import sys
from unittest.mock import patch

import pytest

from constants import BOARD_SIZE, EMPTY, PLAYER, AI, WIN_SCORE, EASY, MEDIUM, HARD, MAX_DEPTH
import board as board_module
from board import (
    create_board, make_move, print_board, get_player_move,
    get_empty_cells, has_neighbor, get_candidate_moves
)
from rules import check_five_from_cell, check_winner, is_board_full
from evaluation import (
    get_all_lines, evaluate_line_for_player,
    evaluate_player, evaluate_board
)
from ai import (
    killer_moves, add_killer_move, find_immediate_winning_moves,
    evaluate_for_ordering_move, order_moves, minimax,
    find_best_move_by_minimax, ai_move
)

# ===================== BOARD TESTS =====================

class TestBoard:
    def test_create_board_returns_15x15(self, empty_board):
        assert len(empty_board) == BOARD_SIZE
        for row in empty_board:
            assert len(row) == BOARD_SIZE
            for cell in row:
                assert cell == EMPTY

    def test_make_move_valid(self, empty_board):
        assert make_move(empty_board, 3, 5, PLAYER) is True
        assert empty_board[3][5] == PLAYER

    def test_make_move_ai(self, empty_board):
        assert make_move(empty_board, 10, 10, AI) is True
        assert empty_board[10][10] == AI

    def test_make_move_occupied(self, empty_board):
        make_move(empty_board, 5, 5, PLAYER)
        assert make_move(empty_board, 5, 5, AI) is False
        assert empty_board[5][5] == PLAYER

    def test_make_move_negative_row(self, empty_board):
        assert make_move(empty_board, -1, 0, PLAYER) is False

    def test_make_move_negative_col(self, empty_board):
        assert make_move(empty_board, 0, -1, PLAYER) is False

    def test_make_move_oob_row(self, empty_board):
        assert make_move(empty_board, BOARD_SIZE, 0, PLAYER) is False

    def test_make_move_oob_col(self, empty_board):
        assert make_move(empty_board, 0, BOARD_SIZE, PLAYER) is False

    def test_print_board_output(self, empty_board):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            make_move(empty_board, 0, 0, PLAYER)
            make_move(empty_board, 1, 1, AI)
            print_board(empty_board)
        finally:
            sys.stdout = sys.__stdout__
        output = captured.getvalue()
        assert "X" in output
        assert "O" in output
        assert "." in output

    def test_get_player_move_valid(self):
        with patch("builtins.input", side_effect=["7", "7"]):
            row, col = get_player_move()
            assert row == 7
            assert col == 7

    def test_get_player_move_invalid_then_valid(self):
        with patch("builtins.input", side_effect=["abc", "7", "7"]):
            row, col = get_player_move()
            assert row == 7
            assert col == 7

    def test_get_empty_cells_empty_board(self, empty_board):
        cells = get_empty_cells(empty_board)
        assert len(cells) == BOARD_SIZE * BOARD_SIZE

    def test_get_empty_cells_after_moves(self, empty_board):
        make_move(empty_board, 0, 0, PLAYER)
        make_move(empty_board, 1, 1, AI)
        make_move(empty_board, 2, 2, PLAYER)
        cells = get_empty_cells(empty_board)
        assert len(cells) == BOARD_SIZE * BOARD_SIZE - 3
        assert (0, 0) not in cells
        assert (1, 1) not in cells

    def test_get_empty_cells_full_board(self, full_board):
        cells = get_empty_cells(full_board)
        assert cells == []

    def test_has_neighbor_false_empty(self, empty_board):
        assert has_neighbor(empty_board, 7, 7, 2) is False

    def test_has_neighbor_true_adjacent(self, empty_board):
        empty_board[7][7] = PLAYER
        assert has_neighbor(empty_board, 7, 8, 1) is True

    def test_has_neighbor_distance_2(self, empty_board):
        empty_board[7][7] = PLAYER
        assert has_neighbor(empty_board, 7, 9, 2) is True

    def test_has_neighbor_distance_2_too_far(self, empty_board):
        empty_board[7][7] = PLAYER
        assert has_neighbor(empty_board, 7, 10, 2) is False

    def test_has_neighbor_corner(self, empty_board):
        empty_board[0][0] = PLAYER
        assert has_neighbor(empty_board, 0, 1, 1) is True

    def test_has_neighbor_self_not_counted(self, empty_board):
        empty_board[7][7] = PLAYER
        assert has_neighbor(empty_board, 7, 7, 1) is False

    def test_get_candidate_moves_empty_board_returns_center(self, empty_board):
        candidates = get_candidate_moves(empty_board)
        assert candidates == [(BOARD_SIZE // 2, BOARD_SIZE // 2)]

    def test_get_candidate_moves_excludes_occupied(self, empty_board):
        empty_board[7][7] = PLAYER
        candidates = get_candidate_moves(empty_board)
        assert (7, 7) not in candidates

    def test_get_candidate_moves_all_empty(self, empty_board):
        empty_board[7][7] = PLAYER
        candidates = get_candidate_moves(empty_board)
        assert all(empty_board[r][c] == EMPTY for r, c in candidates)

    def test_get_candidate_moves_full_board(self, full_board):
        candidates = get_candidate_moves(full_board)
        assert candidates == []


# ===================== RULES TESTS =====================

class TestRules:
    def test_check_five_horizontal(self, board_horizontal_win):
        assert check_five_from_cell(board_horizontal_win, 7, 0, PLAYER) is True

    def test_check_five_vertical(self, board_vertical_win):
        assert check_five_from_cell(board_vertical_win, 0, 7, AI) is True

    def test_check_five_diagonal_down_right(self, board_diagonal_win):
        assert check_five_from_cell(board_diagonal_win, 0, 0, PLAYER) is True

    def test_check_five_anti_diagonal(self, board_anti_diagonal_win):
        r, c = 0, BOARD_SIZE - 1
        assert check_five_from_cell(board_anti_diagonal_win, r, c, AI) is True

    def test_check_five_not_enough(self, board_ai_advantage):
        assert check_five_from_cell(board_ai_advantage, 7, 0, AI) is False

    def test_check_five_blocked_both_sides(self, board_blocked_five):
        assert check_five_from_cell(board_blocked_five, 7, 1, PLAYER) is False

    def test_check_five_at_board_edge(self):
        board = create_board()
        for row in range(5):
            board[BOARD_SIZE - 5 + row][BOARD_SIZE - 1] = PLAYER
        assert check_five_from_cell(board, BOARD_SIZE - 5, BOARD_SIZE - 1, PLAYER) is True

    def test_check_five_empty_board(self, empty_board):
        assert check_five_from_cell(empty_board, 7, 7, PLAYER) is False

    def test_check_winner_player_wins(self, board_horizontal_win):
        assert check_winner(board_horizontal_win, PLAYER) is True

    def test_check_winner_ai_wins(self, board_vertical_win):
        assert check_winner(board_vertical_win, AI) is True

    def test_check_winner_diagonal(self, board_diagonal_win):
        assert check_winner(board_diagonal_win, PLAYER) is True

    def test_check_winner_no_winner_empty(self, empty_board):
        assert check_winner(empty_board, PLAYER) is False
        assert check_winner(empty_board, AI) is False

    def test_check_winner_no_winner_partial(self, board_ai_advantage):
        assert check_winner(board_ai_advantage, AI) is False

    def test_check_winner_other_player_not_win(self, board_horizontal_win):
        assert check_winner(board_horizontal_win, AI) is False

    def test_is_board_full_empty(self, empty_board):
        assert is_board_full(empty_board) is False

    def test_is_board_full_partial(self, board_nearly_full):
        assert is_board_full(board_nearly_full) is False

    def test_is_board_full_full(self, full_board):
        assert is_board_full(full_board) is True


# ===================== EVALUATION TESTS =====================

class TestEvaluation:
    def test_get_all_lines_count(self, empty_board):
        lines = get_all_lines(empty_board)
        assert len(lines) == 72

    def test_get_all_lines_horizontal_length(self, empty_board):
        lines = get_all_lines(empty_board)
        horizontals = lines[:BOARD_SIZE]
        for hl in horizontals:
            assert len(hl) == BOARD_SIZE

    def test_get_all_lines_contains_placed_stone(self, empty_board):
        empty_board[3][5] = PLAYER
        lines = get_all_lines(empty_board)
        row_3 = [empty_board[3][c] for c in range(BOARD_SIZE)]
        assert row_3 in lines
        col_5 = [empty_board[r][5] for r in range(BOARD_SIZE)]
        assert col_5 in lines

    def test_evaluate_line_five(self):
        line = [EMPTY] + [PLAYER] * 5
        score = evaluate_line_for_player(line, PLAYER)
        assert score >= 1000000

    def test_evaluate_line_open_four(self):
        line = [EMPTY, PLAYER, PLAYER, PLAYER, PLAYER, EMPTY]
        score = evaluate_line_for_player(line, PLAYER)
        assert score >= 120000

    def test_evaluate_line_semi_open_four(self):
        line = [AI, PLAYER, PLAYER, PLAYER, PLAYER, EMPTY]
        score = evaluate_line_for_player(line, PLAYER)
        assert score >= 15000

    def test_evaluate_line_broken_four(self):
        line = [EMPTY, PLAYER, PLAYER, PLAYER, EMPTY, PLAYER, EMPTY]
        score = evaluate_line_for_player(line, PLAYER)
        assert score >= 18000

    def test_evaluate_line_open_three(self):
        line = [EMPTY, PLAYER, PLAYER, PLAYER, EMPTY]
        score = evaluate_line_for_player(line, PLAYER)
        assert score >= 5000

    def test_evaluate_line_broken_three(self):
        line = [EMPTY, PLAYER, PLAYER, EMPTY, PLAYER, EMPTY]
        score = evaluate_line_for_player(line, PLAYER)
        assert score >= 3500

    def test_evaluate_line_open_two(self):
        line = [EMPTY, PLAYER, PLAYER, EMPTY]
        score = evaluate_line_for_player(line, PLAYER)
        assert score >= 300

    def test_evaluate_line_open_one(self):
        line = [EMPTY, PLAYER, EMPTY]
        score = evaluate_line_for_player(line, PLAYER)
        assert score >= 10

    def test_evaluate_line_empty(self):
        line = [EMPTY] * 5
        score = evaluate_line_for_player(line, PLAYER)
        assert score == 0

    def test_evaluate_line_opponent_stones_treated_as_block(self):
        line = [AI, AI, AI, AI, AI]
        score = evaluate_line_for_player(line, PLAYER)
        assert score == 0

    def test_evaluate_player_empty(self, empty_board):
        assert evaluate_player(empty_board, PLAYER) == 0
        assert evaluate_player(empty_board, AI) == 0

    def test_evaluate_player_non_zero(self, board_ai_advantage):
        score = evaluate_player(board_ai_advantage, AI)
        assert score > 0

    def test_evaluate_player_player_non_zero(self, board_horizontal_win):
        score = evaluate_player(board_horizontal_win, PLAYER)
        assert score > 0

    def test_evaluate_board_empty(self, empty_board):
        assert evaluate_board(empty_board) == 0

    def test_evaluate_board_ai_advantage(self, board_ai_advantage):
        assert evaluate_board(board_ai_advantage) > 0

    def test_evaluate_board_player_advantage(self, board_horizontal_win):
        assert evaluate_board(board_horizontal_win) < 0


# ===================== AI TESTS =====================

class TestAI:
    def test_killer_moves_initial_state(self):
        for d in range(MAX_DEPTH + 1):
            assert killer_moves[d] == []

    def test_add_killer_move_basic(self):
        add_killer_move(1, (3, 4))
        assert killer_moves[1] == [(3, 4)]

    def test_add_killer_move_front(self):
        add_killer_move(1, (3, 4))
        add_killer_move(1, (5, 6))
        assert killer_moves[1][0] == (5, 6)

    def test_add_killer_move_dedup(self):
        add_killer_move(1, (3, 4))
        add_killer_move(1, (3, 4))
        assert len(killer_moves[1]) == 1

    def test_add_killer_move_max_two(self):
        add_killer_move(1, (1, 1))
        add_killer_move(1, (2, 2))
        add_killer_move(1, (3, 3))
        assert len(killer_moves[1]) == 2
        assert killer_moves[1] == [(3, 3), (2, 2)]

    def test_add_killer_move_depth_independent(self):
        add_killer_move(1, (3, 4))
        add_killer_move(2, (5, 6))
        assert killer_moves[1] == [(3, 4)]
        assert killer_moves[2] == [(5, 6)]

    def test_find_immediate_winning_moves_ai(self, board_ai_advantage):
        # AI has 4 in a row at cols 0-3, col 4 is empty
        moves = find_immediate_winning_moves(board_ai_advantage, AI)
        assert (7, 4) in moves

    def test_find_immediate_winning_moves_empty(self, empty_board):
        assert find_immediate_winning_moves(empty_board, AI) == []

    def test_find_immediate_winning_moves_player_block(self, board_ai_advantage):
        # AI has 4 in a row; flip them to PLAYER to test blocking
        for col in range(4):
            board_ai_advantage[7][col] = PLAYER
        moves = find_immediate_winning_moves(board_ai_advantage, PLAYER)
        assert (7, 4) in moves

    def test_evaluate_for_ordering_no_killer(self, empty_board):
        score = evaluate_for_ordering_move(empty_board, 7, 7, AI, 1)
        assert score < 10**8

    def test_evaluate_for_ordering_killer_bonus(self, empty_board):
        add_killer_move(1, (7, 7))
        score = evaluate_for_ordering_move(empty_board, 7, 7, AI, 1)
        assert score >= 10**8

    def test_evaluate_for_ordering_winning_move(self, board_ai_advantage):
        score = evaluate_for_ordering_move(board_ai_advantage, 7, 4, AI, 1)
        assert score >= 10**9

    def test_evaluate_for_ordering_center_bonus(self, empty_board):
        center = (7, 7)
        corner = (0, 0)
        center_score = evaluate_for_ordering_move(empty_board, center[0], center[1], AI, 1)
        corner_score = evaluate_for_ordering_move(empty_board, corner[0], corner[1], AI, 1)
        assert center_score > corner_score

    def test_evaluate_for_ordering_ally_neighbors(self, empty_board):
        empty_board[7][6] = AI
        with_neighbor = evaluate_for_ordering_move(empty_board, 7, 7, AI, 1)
        empty_board[7][6] = EMPTY
        without = evaluate_for_ordering_move(empty_board, 7, 7, AI, 1)
        assert with_neighbor >= without + 10

    def test_order_moves_descending(self, empty_board):
        empty_board[7][7] = AI
        candidates = [(7, 6), (7, 8), (7, 7)]
        ordered = order_moves(empty_board, candidates, AI, 1)
        assert len(ordered) == 3
        assert all(m in candidates for m in ordered)

    def test_minimax_ai_wins(self):
        board = create_board()
        for col in range(5):
            board[7][col] = AI
        value = minimax(board, 1, True, float("-inf"), float("inf"))
        assert value == WIN_SCORE

    def test_minimax_player_wins(self, board_horizontal_win):
        value = minimax(board_horizontal_win, 1, False, float("-inf"), float("inf"))
        assert value == -WIN_SCORE

    def test_minimax_full_board(self):
        board = create_board()
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                board[r][c] = PLAYER if r < BOARD_SIZE // 2 else AI
        value = minimax(board, 1, True, float("-inf"), float("inf"))
        assert value in (WIN_SCORE, -WIN_SCORE, 0)

    def test_minimax_depth_zero(self, empty_board):
        value = minimax(empty_board, 0, True, float("-inf"), float("inf"))
        expected = evaluate_board(empty_board)
        assert value == expected

    def test_minimax_depth_one_ai(self, empty_board):
        value = minimax(empty_board, 1, True, float("-inf"), float("inf"))
        assert -WIN_SCORE < value < WIN_SCORE

    def test_minimax_depth_one_player(self, empty_board):
        value = minimax(empty_board, 1, False, float("-inf"), float("inf"))
        assert -WIN_SCORE < value < WIN_SCORE

    def test_find_best_move_by_minimax_empty(self, empty_board):
        move = find_best_move_by_minimax(empty_board, 1)
        assert move is not None
        r, c = move
        assert 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE
        assert empty_board[r][c] == EMPTY

    def test_find_best_move_by_minimax_full(self, full_board):
        move = find_best_move_by_minimax(full_board, 1)
        assert move is None

    def test_find_best_move_by_minimax_immediate_ai_win(self):
        board = create_board()
        for col in range(4):
            board[7][col] = AI
        move = find_best_move_by_minimax(board, 1)
        assert move == (7, 4)

    def test_find_best_move_by_minimax_immediate_block(self):
        board = create_board()
        for col in range(4):
            board[7][col] = PLAYER
        move = find_best_move_by_minimax(board, 1)
        assert move is not None
        r, c = move

    def test_find_best_move_by_minimax_depth_1(self, empty_board):
        move = find_best_move_by_minimax(empty_board, 1)
        assert move is not None

    def test_find_best_move_by_minimax_depth_2(self, empty_board):
        move = find_best_move_by_minimax(empty_board, 2)
        assert move is not None

    def test_find_best_move_by_minimax_depth_3(self, empty_board):
        move = find_best_move_by_minimax(empty_board, 3)
        assert move is not None

    def test_ai_move_easy(self, empty_board):
        move = ai_move(empty_board, EASY)
        assert move is not None

    def test_ai_move_medium(self, empty_board):
        move = ai_move(empty_board, MEDIUM)
        assert move is not None

    def test_ai_move_hard(self, empty_board):
        move = ai_move(empty_board, HARD)
        assert move is not None

    def test_ai_move_full_board(self, full_board):
        move = ai_move(full_board, EASY)
        assert move is None
        move = ai_move(full_board, MEDIUM)
        assert move is None
        move = ai_move(full_board, HARD)
        assert move is None

    def test_ai_move_valid_empty_cell(self, empty_board):
        move = ai_move(empty_board, HARD)
        assert move is not None
        r, c = move
        assert empty_board[r][c] == EMPTY
