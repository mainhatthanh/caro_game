# Caro Game — Gomoku AI with Pre-Search Threat Pipeline

A Caro (Gomoku) AI engine with a pre-search threat detection pipeline, alpha-beta minimax search with iterative deepening, Zobrist transposition table, and a tournament simulation framework.

## Project Structure

```
caro_game/
├── main.py           # Console-based game (terminal UI)
├── ui.py             # Tkinter GUI game (desktop app)
├── ai.py             # AI engine core — search + threat pipeline
├── evaluation.py     # Board evaluation — run-length pattern scoring
├── zobrist.py        # Zobrist hashing + transposition table
├── board.py          # Board creation, move generation, candidate moves
├── rules.py          # Win detection, draw check
├── constants.py      # All config values, priorities, categories
├── simulation/
│   └── simulate.py   # AI-vs-AI tournament simulation GUI
└── test/             # Pytest test suite
```

---

## 1. Console Game — `main.py`

```
python main.py
```

A terminal-based game where you play as X against the AI.

1. Enter a difficulty level (1=Easy, 2=Medium, 3=Hard)
2. Enter row (0-14) and column (0-14) for your move
3. AI responds automatically
4. Game ends when a player wins or the board is full

Difficulty maps directly to search depth:
- **Easy** = depth 1 (shallow search, weak)
- **Medium** = depth 2
- **Hard** = depth 3+ (up to MAX_DEPTH=5 with iterative deepening)

---

## 2. Desktop GUI — `ui.py`

```
python ui.py
```

A Tkinter GUI with gradient menu and themed game board.

### Gameplay
- Click **Easy/Medium/Hard** on the menu to start
- Click any empty cell to place your X
- AI (O) responds after a 300ms delay
- Use **← Back to Menu** to return and change difficulty
- Win/loss is shown in a popup message box

### Themes
| Difficulty | Board Color | Grid | X Color | O Color |
|-----------|-------------|------|---------|---------|
| Easy | Dark green | Green | Bright green | White |
| Medium | Dark blue | Purple | Blue | White |
| Hard | Dark red | Red | Red | White |

### How the GUI works
- `CaroApp` is the root window, managing two frames: `MenuFrame` and `GameFrame`
- `MenuFrame` draws a gradient with 3 buttons
- `GameFrame` draws the board grid and handles clicks
- `after(300, ai_turn)` delays the AI move so the board redraws before thinking

---

## 3. AI Tournament Simulation — `simulation/simulate.py`

```
python simulation/simulate.py
```

A standalone Tkinter GUI for running AI-vs-AI matches with full feature toggles, softmax randomness, parallel execution, live board display, and detailed logging.

### Configuration (per AI)
| Control | Description |
|---------|-------------|
| Name | Label for display and logging |
| Zobrist/TT | Enable Zobrist hashing + transposition table |
| Iterative Deepening | Aspiration window ID search |
| LMR | Late Move Reduction (prunes late moves at depth ≥ 3) |
| Candidate Limiting | Cap candidate moves by depth (24 / 18 / 14) |
| Killer Heuristic | Store killer moves per depth for move ordering |
| Move Ordering | Sort candidates by threat/block/center score |
| Threat Detection | Pre-search pipeline for forks & immediate wins |
| Depth | Search depth (1-5) |
| Softmax | Temperature for random move picking (0=deterministic) |
| Rand/match | Randomize softmax per match |

### Controls
| Button | Action |
|--------|--------|
| **Start** | Begin tournament with current configs |
| **Stop** | Terminate all running matches |
| **Switch Display** | Cycle through match boards (iterative, not random) |
| **Replay** | Step through the current match move by move |
| **Pause/Resume** | Pause/resume replay |
| **Speed** | Slider (0.05s–1.0s delay per replay step) |

### How it works
1. Each AI has independent feature toggles, search depth, and softmax
2. Matches alternate who plays first (odd matches = AI1 first)
3. Each match runs in a `multiprocessing.Process` (spawn start method)
4. The engine always plays as AI (-1). When the engine needs to play as PLAYER (1), `swap_board()` is called to mirror the board so the engine evaluates correctly
5. Display events stream through a `multiprocessing.Queue` for live board updates
6. Results are written per-match as `.log` files and aggregated as `summary.json`

### Understanding the board display
- **Black circles (●)** = PLAYER (1) — stones drawn as filled black ovals
- **White circles (○)** = AI (-1) — stones drawn as white ovals with black outline
- **Red dot** = most recent move
- Label shows who plays each color based on `ai1_first` flag

### Log output
```
simulation/logs/{session_timestamp}/
├── match_000.log       # Per-match human-readable log
├── match_001.log
├── ...
├── summary.json        # Aggregated results + all move data
└── errors.log          # Subprocess crash traces
```

### Example: ablation study
To test the impact of the Zobrist transposition table:
- AI1: all features ON (control)
- AI2: only Zobrist/TT OFF
- Run 20+ matches
- Compare win rate and avg time per move in summary.json

---

## AI Engine Architecture

### Pre-Search Threat Pipeline (`ai.py:find_best_move_by_minimax`)

Before entering iterative deepening search, the engine scans all candidate moves for tactical patterns. Moves are scored with a priority system where **lower number = more urgent**:

| Priority | Condition | Action |
|----------|-----------|--------|
| 1-2 | AI immediate win (5 in a row) | Play immediately |
| 3-4 | Opponent immediate win | Block immediately |
| 5 | Opponent would win if AI plays here | Block (pre-search) |
| 9 | Opponent open-four | Must block |
| 10 | AI creates five | Attack |
| 15 | Opponent double-four fork | Block fork |
| 18 | Opponent four-three fork | Block fork |
| 20 | AI double-four fork | Attack |
| 22 | AI four-three fork | Attack |
| 23 | Opponent double-three fork | Block fork |
| 24 | AI open-four | Attack |
| 26 | Opponent semi-open-four | Block |
| 29 | AI double-three fork | Attack |
| 34 | AI semi-open-four | Attack |
| 35 | Opponent open-three | Block |
| 36 | AI open-three | Attack |
| — | No threat found | Fall through to search |

The pipeline compares attack vs defense priority. Defense wins if it's strictly more urgent (lower number). If tied, falls through to iterative deepening search.

### Fork Detection

`detect_fork()` scans all 4 axes through a candidate cell, classifies each axis by threat category (FIVE, OPEN_FOUR, SEMI_OPEN_FOUR, OPEN_THREE, SEMI_OPEN_THREE), then combines them:

- **Double-four** (2+ axes with four) → FORK_DOUBLE_FOUR
- **Four-three** (1 four-axis + 1 three-axis) → FORK_FOUR_THREE
- **Double-three** (2+ axes with three) → FORK_DOUBLE_THREE

Both open and semi-open threats count toward fork classification.

### Search

- **Iterative Deepening**: Searches from depth 1 up to the target, using aspiration windows (narrow alpha-beta bounds from previous depth's score). Re-searches with full window on fail.
- **Late Move Reduction**: At depth ≥ 3, moves after the 6th are searched at reduced depth first. If promising, they're re-searched at full depth.
- **Candidate Limiting**: Caps the number of moves searched per depth tier (24 early, 18 mid, 14 deep).
- **Quiescence Search**: At leaf nodes, extends search on threatening moves (fours and open-threes) to avoid the horizon effect.
- **Move Ordering**: Scores each candidate by: wins > blocks > threats > killer moves > history > neighbor density > center proximity.
- **Transposition Table**: Zobrist 64-bit hash with depth-preferred replacement. Stores EXACT/LOWERBOUND/UPPERBOUND flags for alpha-beta pruning.

### Board Evaluation

`evaluate_board()` uses run-length analysis on all 4 directions (horizontal, vertical, 2 diagonals):

1. Finds all contiguous runs of player stones
2. Scores each run by length and open-end count (both/single/none)
3. Scores broken patterns (2 runs separated by exactly 1 empty cell)
4. Returns `ai_score - 1.5 * player_score` (the 1.5x factor makes the AI defend more aggressively)

Old 49-string-pattern matching was replaced with this O(n) scan for speed and accuracy.
