"""Constants and configuration for the Caro (Gomoku) AI engine.

This module defines every tunable parameter in one place:
- Board size, player values, and base scoring
- Threat/fork classification constants
- Pattern scores used by the evaluation function
- Compound (fork) scores for multi-axis threats
- Move ordering priorities (higher = searched first)
- Search optimization parameters (aspiration window, LMR, candidate limits)
- Quiescence search and transposition table limits
"""

BOARD_SIZE = 15

# ---------------------------------------------------------------------------
# Cell values — the board is a 2D list of these constants
# ---------------------------------------------------------------------------
EMPTY = 0
PLAYER = 1
AI = - 1

# Base score for a winning position in minimax.
# Orders of magnitude above any positional score so search terminates instantly.
WIN_SCORE = 10**9

# Maximum search depth for "Hard" difficulty (depth 3).
# Iterative deepening starts from 1 and goes up to this.
MAX_DEPTH = 5

# Depth presets for difficulty levels (exposed to the console game).
EASY = 1
MEDIUM = 2
HARD = 3

# ---------------------------------------------------------------------------
# Fork type classifications (returned by detect_fork)
# ---------------------------------------------------------------------------
# These indicate compound threats across multiple axes, ordered by severity:
#   DOUBLE_FOUR > FOUR_THREE > DOUBLE_THREE > NONE
# They help the pre-search pipeline prioritize moves that create or block forks.
FORK_NONE = 0
FORK_DOUBLE_FOUR = 1       # Two axes with open-four (opponent can block only one)
FORK_FOUR_THREE = 2         # One open-four + one open-three on different axes
FORK_DOUBLE_THREE = 3       # Two axes with open-three

# ---------------------------------------------------------------------------
# Threat categories for axis classification (per-axis, not compound)
# ---------------------------------------------------------------------------
# Used by both classify_axis() and the evaluation function to describe
# the threat level of a single direction through a cell.
THREAT_NONE = 0
THREAT_FIVE = 1               # Five+ in a row (winning)
THREAT_OPEN_FOUR = 2          # 4 stones, both ends open (.MMMM.)
THREAT_SEMI_OPEN_FOUR = 3     # 4 stones, one end open (EMMMM. or .MMMME)
THREAT_BROKEN_FOUR = 4        # 4 stones with a gap (.MMM.M. pattern)
THREAT_OPEN_THREE = 5         # 3 stones, both ends open (.MMM.)
THREAT_SEMI_OPEN_THREE = 6    # 3 stones, one end open (EMMM. or .MMME)
THREAT_BROKEN_THREE = 7       # 3 stones with a gap (.MM.M. pattern)
THREAT_OPEN_TWO = 8           # 2 stones, both ends open (.MM.)

# ---------------------------------------------------------------------------
# Pattern scores — used by the evaluation function (evaluate_line_for_player).
# These quantify the "value" of stone configurations on a single line.
# The ratios between tiers matter more than absolute values:
#   FIVE >> OPEN_FOUR >> SEMI_OPEN_FOUR ~ BROKEN_FOUR >> OPEN_THREE >> ...
# ---------------------------------------------------------------------------
PATTERN_SCORES = {
    "FIVE": 1000000,                # Game-ending — evaluation-trivial
    "OPEN_FOUR": 120000,            # Unblockable (if not blocked next move)
    "SEMI_OPEN_FOUR": 15000,        # One-move threat
    "BROKEN_FOUR": 18000,           # Gap-4 — often as dangerous as semi-open
    "SEMI_BROKEN_FOUR": 6000,
    "OPEN_THREE": 5000,             # Buildable to four
    "BROKEN_THREE": 3500,
    "SEMI_OPEN_THREE": 800,
    "OPEN_TWO": 300,
    "BROKEN_TWO": 150,
    "SEMI_OPEN_TWO": 50,
    "OPEN_ONE": 10,                 # Minimal influence
}

# ---------------------------------------------------------------------------
# Compound (fork) scores — used when evaluating multi-axis threats.
# These sit between FIVE and OPEN_FOUR in magnitude because a fork is
# nearly as decisive as a direct win (opponent can't block both axes).
# ---------------------------------------------------------------------------
COMPOUND_SCORES = {
    "DOUBLE_FOUR": 250000,          # Two open-fours — guaranteed win
    "FOUR_THREE": 100000,           # Four on one axis, three on another
    "DOUBLE_THREE": 30000,          # Two open-threes — very dangerous
}

# ---------------------------------------------------------------------------
# Move ordering priorities — higher values are searched first.
# These are used by evaluate_for_ordering_move() to sort the candidate list
# before alpha-beta search, improving pruning efficiency.
# ---------------------------------------------------------------------------
MOVE_PRIORITY_WIN = 10**9            # Immediate win — search first
MOVE_PRIORITY_BLOCK_WIN = 2 * 10**8  # Block opponent immediate win
MOVE_PRIORITY_THREAT = 10**7         # Creates open-four or broken-four
MOVE_PRIORITY_BLOCK_THREAT = 10**6   # Blocks opponent's threat
MOVE_PRIORITY_KILLER = 10**5         # Killer move bonus (from beta cutoffs)

# ---------------------------------------------------------------------------
# Search optimization parameters
# ---------------------------------------------------------------------------

# Aspiration window half-width for iterative deepening.
# After the first depth, we search with [prev_score - WINDOW, prev_score + WINDOW].
# If the score falls outside this range, we re-search with full width.
# 50000 is ~half the value of an open-three, so most moves won't fail-soft.
ASPIRATION_WINDOW = 50000

# Late Move Reduction (LMR) parameters.
# Moves searched later in the ordering are reduced in depth.
# If the reduced search beats alpha, we re-search at full depth.
LMR_DEPTH_THRESHOLD = 3     # Don't apply LMR below this depth
LMR_MOVES_THRESHOLD = 6     # First N moves always at full depth
LMR_REDUCTION = 1           # How many plies to reduce

# Candidate move limits — reduce branching factor by capping how many
# moves are considered at each depth tier. Helps control search explosion.
CANDIDATE_LIMIT_DEPTH_EARLY = 2     # Depth boundary for "early" tier
CANDIDATE_LIMIT_DEPTH_MID = 4       # Depth boundary for "mid" tier
CANDIDATE_LIMIT_EARLY = 24          # Max candidates at depths 1-2
CANDIDATE_LIMIT_MID = 18            # Max candidates at depths 3-4
CANDIDATE_LIMIT_DEEP = 14           # Max candidates at depth 5+

# Quiescence search — extend search at leaf nodes when threats exist.
# Without this, the horizon effect hides tactical sequences just below
# the search depth.
QUIESCENCE_DEPTH = 3               # Max extra plies for quiescence

# Transposition table — prevents re-searching identical positions.
# Stores ~1M entries before eviction kicks in.
TT_SIZE_LIMIT = 1000000
