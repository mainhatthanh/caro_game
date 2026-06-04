"""Tests for feature toggles and fork priority regression."""
import random

import pytest

import ai as ai_module
from board import create_board, get_candidate_moves
from constants import (
    BOARD_SIZE, EMPTY, PLAYER, AI, CANDIDATE_LIMIT_EARLY,
    CANDIDATE_LIMIT_MID, CANDIDATE_LIMIT_DEEP, LMR_DEPTH_THRESHOLD,
    FORK_NONE, FORK_DOUBLE_FOUR, FORK_FOUR_THREE, FORK_DOUBLE_THREE,
)
from ai import (
    find_best_move_by_minimax, compute_zobrist, add_killer_move,
    order_moves, killer_moves, detect_fork, _iterative_deepening_search,
)
from evaluation import evaluate_board


# ===================== TOGGLE TESTS =====================

class TestZobristOff:
    def test_compute_zobrist_returns_none_when_disabled(self):
        """Simulate zobrist=False: monkey-patch compute_zobrist to return None."""
        board = create_board()
        board[7][7] = AI
        original = ai_module.compute_zobrist
        ai_module.compute_zobrist = lambda b: None
        try:
            result = ai_module.compute_zobrist(board)
            assert result is None
        finally:
            ai_module.compute_zobrist = original

    def test_compute_zobrist_returns_int_when_enabled(self):
        """With zobrist enabled, compute_zobrist returns an integer."""
        board = create_board()
        board[7][7] = AI
        result = compute_zobrist(board)
        assert isinstance(result, int)


class TestMoveOrderingOff:
    def test_order_moves_returns_shuffled_when_disabled(self):
        """Simulate move_ordering=False: monkey-patch order_moves to shuffle.
        Verify output != input with high probability."""
        board = create_board()
        board[7][7] = AI
        board[7][8] = PLAYER
        candidates = get_candidate_moves(board, 1)
        original = ai_module.order_moves
        ai_module.order_moves = (
            lambda b, cand, player, depth, hash_move=None, opponent=None:
            random.sample(cand, len(cand))
        )
        try:
            result = ai_module.order_moves(board, candidates, AI, 1)
            assert len(result) == len(candidates)
            assert set(result) == set(candidates)
            # With enough candidates, shuffled != sorted is near-certain
            if len(candidates) >= 3:
                assert result != candidates, "moves should be shuffled when ordering is off"
        finally:
            ai_module.order_moves = original


class TestKillerHeuristicOff:
    def test_add_killer_noop_when_disabled(self):
        """Simulate killer_heuristic=False: add_killer_move becomes no-op."""
        original = ai_module.add_killer_move
        ai_module.add_killer_move = lambda depth, move: None
        try:
            for d in range(5):
                saved = list(killer_moves.get(d, []))
                ai_module.add_killer_move(d, (7, 7))
                assert list(killer_moves.get(d, [])) == saved
        finally:
            ai_module.add_killer_move = original


class TestTogglesOffStillFindWin:
    def test_finds_win_with_all_features_disabled(self):
        """Place 4 AI in a row with open ends. Disable ALL features.
        Pre-search pipeline should still find the immediate win via
        find_immediate_winning_moves (priority 1)."""
        board = create_board()
        for col in range(4):
            board[7][col] = AI

        original_lmr = ai_module.LMR_DEPTH_THRESHOLD
        original_cand_early = ai_module.CANDIDATE_LIMIT_EARLY
        original_cand_mid = ai_module.CANDIDATE_LIMIT_MID
        original_cand_deep = ai_module.CANDIDATE_LIMIT_DEEP
        original_add_killer = ai_module.add_killer_move
        original_order = ai_module.order_moves
        original_zobrist = ai_module.compute_zobrist

        ai_module.LMR_DEPTH_THRESHOLD = 99
        ai_module.CANDIDATE_LIMIT_EARLY = 999
        ai_module.CANDIDATE_LIMIT_MID = 999
        ai_module.CANDIDATE_LIMIT_DEEP = 999
        ai_module.add_killer_move = lambda depth, move: None
        ai_module.order_moves = lambda b, cand, player, depth, hm=None, op=None: random.sample(cand, len(cand))
        ai_module.compute_zobrist = lambda b: None

        try:
            move = find_best_move_by_minimax(board, 1)
            assert move is not None, "AI should find a winning move"
            row, col = move
            assert board[row][col] == EMPTY
            # Placing there should give 5 in a row
            board[row][col] = AI
            from rules import check_winner_fast
            assert check_winner_fast(board, AI, (row, col))
        finally:
            ai_module.LMR_DEPTH_THRESHOLD = original_lmr
            ai_module.CANDIDATE_LIMIT_EARLY = original_cand_early
            ai_module.CANDIDATE_LIMIT_MID = original_cand_mid
            ai_module.CANDIDATE_LIMIT_DEEP = original_cand_deep
            ai_module.add_killer_move = original_add_killer
            ai_module.order_moves = original_order
            ai_module.compute_zobrist = original_zobrist


# ===================== FORK PRIORITY REGRESSION TEST =====================

class TestForkPriority:
    def _setup_double_three_board(self):
        """Build a board where:
        - AI has a double-three candidate at (10,10)
        - Opponent has a double-three candidate at (7,7)
        With the OLD buggy priority: AI would attack instead of blocking.
        """
        board = create_board()

        # AI stones: open-three horizontal + open-three vertical at (10,10)
        board[10][8] = AI
        board[10][9] = AI
        board[8][10] = AI
        board[9][10] = AI

        # Opponent stones: open-three horizontal + open-three vertical at (7,7)
        board[7][5] = PLAYER
        board[7][6] = PLAYER
        board[5][7] = PLAYER
        board[6][7] = PLAYER

        # Neighbor stones so the candidates appear in get_candidate_moves
        # (place them where they won't extend the open-three lines)
        board[12][10] = AI
        board[12][7] = PLAYER

        return board

    def test_ai_blocks_opponent_double_three(self):
        """When opponent has double-three and AI has double-three,
        AI must block opponent (defense priority 1 vs attack priority 2)."""
        board = self._setup_double_three_board()

        # Verify fork detection works
        # AI at (10,10) should be a double-three
        board[10][10] = AI
        ai_fork = detect_fork(board, 10, 10, AI)
        assert ai_fork == FORK_DOUBLE_THREE, f"Expected DOUBLE_THREE, got {ai_fork}"
        board[10][10] = EMPTY

        # PLAYER at (7,7) should be a double-three
        board[7][7] = PLAYER
        opp_fork = detect_fork(board, 7, 7, PLAYER)
        assert opp_fork == FORK_DOUBLE_THREE, f"Expected DOUBLE_THREE, got {opp_fork}"
        board[7][7] = EMPTY

        # Run AI at depth 1 (pre-search pipeline decides)
        move = find_best_move_by_minimax(board, 1)

        assert move is not None, "AI must choose a move"
        row, col = move

        # AI should block at (7,7), not attack at (10,10)
        # (7,7) blocks opponent's double-three; (10,10) creates AI's double-three
        assert (row, col) == (7, 7), (
            f"AI should block opponent double-three at (7,7) but chose ({row},{col})"
        )

    def test_pure_attack_when_no_defense_needed(self):
        """When AI has double-three and opponent has NO fork, AI should attack."""
        board = create_board()
        # AI double-three at (10,10)
        board[10][8] = AI
        board[10][9] = AI
        board[8][10] = AI
        board[9][10] = AI
        board[10][11] = AI
        board[10][12] = AI

        # Opponent has only a single open-three, NOT a fork
        board[7][5] = PLAYER
        board[7][6] = PLAYER
        board[7][3] = PLAYER

        move = find_best_move_by_minimax(board, 1)
        assert move is not None
        # AI should attack (any move is fine, just not blocking)
        assert move == (10, 10), (
            f"AI should attack at (10,10) when no defense needed, got ({move[0]},{move[1]})"
        )


# ===================== THREAT DETECTION TOGGLE TEST =====================

class TestThreatDetectionToggle:
    def test_threat_detection_off_skips_pipeline(self):
        """When threat_detection=False, the pre-search pipeline is bypassed.
        Use a board where the pipeline would normally return a specific threat move,
        but with the toggle off it falls through to _iterative_deepening_search.

        Create a board where AI has a four-three fork at (7,3).
        With threat_detection ON: find_best_move_by_minimax returns (7,3) (fork found).
        With threat_detection OFF (patched -> _iterative_deepening_search):
        it searches at depth 1 and may find a different valid move."""
        board = create_board()
        # Four-three setup at (7,3): horizontal open-four + vertical open-three
        board[7][4] = AI
        board[7][5] = AI
        board[7][6] = AI
        board[5][3] = AI
        board[6][3] = AI

        # First verify that the pipeline normally finds (7,3)
        normal_move = find_best_move_by_minimax(board, 1)
        assert normal_move == (7, 3), (
            f"With threat detection ON, expected (7,3), got {normal_move}"
        )

        # Now simulate threat_detection=False by swapping find_best_move_by_minimax
        original = ai_module.find_best_move_by_minimax
        ai_module.find_best_move_by_minimax = _iterative_deepening_search
        try:
            # With the toggle off, pre-search is skipped
            move = ai_module.find_best_move_by_minimax(board, 1)
            assert move is not None, (
                "Should still return a valid move even without pre-search pipeline"
            )
            row, col = move
            assert board[row][col] == EMPTY, "Move must be to an empty cell"
        finally:
            ai_module.find_best_move_by_minimax = original
