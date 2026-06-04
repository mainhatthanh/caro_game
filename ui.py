"""Caro Game Desktop GUI — Tkinter application with difficulty selection and themed play.

The GUI has two screens:
1. MenuFrame: gradient background with 3 difficulty buttons (Easy/Medium/Hard)
2. GameFrame: board grid, stone rendering, AI turn handling

Game flow: player clicks → stone placed → check win → after(300ms) AI responds
The 300ms delay allows the UI to redraw the player's stone before AI calculation.
"""

import tkinter as tk
from tkinter import messagebox
from constants import BOARD_SIZE, PLAYER, AI, EASY, MEDIUM, HARD
from board import create_board, make_move
from rules import check_winner, is_board_full
from ai import ai_move

CELL_SIZE = 600 // BOARD_SIZE

# Theme colors per difficulty — each has own palette for visual distinction
THEMES = {
    EASY: {"bg": "#1f2f1f", "board": "#2e4d2e", "grid": "#88cc88", "x": "#00ff88", "o": "#ffffff"},
    MEDIUM: {"bg": "#1e1e2f", "board": "#2b2b3c", "grid": "#6666aa", "x": "#4da6ff", "o": "#ffffff"},
    HARD: {"bg": "#2a1a1a", "board": "#3b1f1f", "grid": "#ff5555", "x": "#ff4d4d", "o": "#ffffff"}
}


# ================= APPLICATION ROOT =================

class CaroApp(tk.Tk):
    """Root window managing navigation between MenuFrame and GameFrame.

    Uses tkraise() to switch frames without destroying/recreating them,
    preserving game state when returning to the menu.
    """

    def __init__(self):
        super().__init__()
        self.title("Caro Game Pro")
        self.geometry("700x780")
        self.resizable(False, False)

        container = tk.Frame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}

        for F in (MenuFrame, GameFrame):
            frame = F(container, self)
            self.frames[F] = frame
            frame.place(relwidth=1, relheight=1)

        self.show_frame(MenuFrame)

    def show_frame(self, frame_class):
        """Bring the specified frame to the front (tkraise pattern)."""
        self.frames[frame_class].tkraise()

    def start_game(self, difficulty):
        """Start a new game with the chosen difficulty and switch to GameFrame."""
        self.frames[GameFrame].start_new_game(difficulty)
        self.show_frame(GameFrame)


# ================= MENU SCREEN =================

class MenuFrame(tk.Frame):
    """Main menu with gradient background and 3 difficulty buttons.

    Each button has hover highlight and click → controller.start_game().
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.draw_gradient()

        self.canvas.create_text(350, 120,
                                text="CARO GAME",
                                fill="white",
                                font=("Segoe UI", 32, "bold"))

        self.canvas.create_text(350, 180,
                                text="Select Difficulty",
                                fill="#cccccc",
                                font=("Segoe UI", 16))

        self.create_button(350, 300, "Easy", EASY, "#4CAF50")
        self.create_button(350, 390, "Medium", MEDIUM, "#2196F3")
        self.create_button(350, 480, "Hard", HARD, "#f44336")

    def draw_gradient(self):
        """Draw a vertical gradient background (dark blue-ish top to bottom)."""
        for i in range(800):
            r = int(20 + i * 0.05)
            g = 20
            b = int(40 + i * 0.1)
            color = f'#{r:02x}{g:02x}{b:02x}'
            self.canvas.create_line(0, i, 700, i, fill=color)

    def lighten(self, color):
        """Lighten a hex color by 40 per channel (for hover effect)."""
        color = color.lstrip('#')
        r, g, b = [int(color[i:i+2], 16) for i in (0, 2, 4)]
        r = min(255, r + 40)
        g = min(255, g + 40)
        b = min(255, b + 40)
        return f'#{r:02x}{g:02x}{b:02x}'

    def create_button(self, x, y, text, value, color):
        """Create a rounded-rectangle button on the menu canvas.

        Binds hover (Enter/Leave) and click events to both the rectangle
        and the text, so clicking anywhere on the button triggers the action.
        """
        w, h = 260, 60

        rect = self.canvas.create_rectangle(
            x - w//2, y - h//2,
            x + w//2, y + h//2,
            fill=color, outline=""
        )

        label = self.canvas.create_text(
            x, y,
            text=text,
            fill="white",
            font=("Segoe UI", 16, "bold")
        )

        def on_enter(e):
            self.canvas.itemconfig(rect, fill=self.lighten(color))

        def on_leave(e):
            self.canvas.itemconfig(rect, fill=color)

        def on_click(e):
            self.controller.start_game(value)

        for item in (rect, label):
            self.canvas.tag_bind(item, "<Enter>", on_enter)
            self.canvas.tag_bind(item, "<Leave>", on_leave)
            self.canvas.tag_bind(item, "<Button-1>", on_click)


# ================= GAME SCREEN =================

class GameFrame(tk.Frame):
    """Game board with click handling, AI turn, and themed rendering.

    Drawing:
    - Grid lines on a Canvas (600x600 px)
    - PLAYER (1) stones as X marks colored per theme
    - AI (-1) stones as circles (white oval outline per theme)

    Flow:
    click → make_move() → check_winner() → after(300, ai_turn)
    The after() gives the UI time to redraw before AI computes.
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.waiting_for_ai = False

        self.canvas = tk.Canvas(self, width=600, height=600, highlightthickness=0)
        self.canvas.pack(pady=10)

        self.status = tk.Label(self, font=("Segoe UI", 12))
        self.status.pack()

        self.back_btn_canvas = None  # recreated per game

        self.canvas.bind("<Button-1>", self.click)

    def start_new_game(self, difficulty):
        """Reset board, apply theme, and redraw for a new game."""
        self.difficulty = difficulty
        self.theme = THEMES[difficulty]

        self.board = create_board()
        self.game_over = False
        self.waiting_for_ai = False

        self.configure(bg=self.theme["bg"])
        self.canvas.config(bg=self.theme["board"])
        self.status.config(bg=self.theme["bg"], fg="white")

        # Recreate back button (destroyed when returning to menu)
        if self.back_btn_canvas:
            self.back_btn_canvas.destroy()
        self.create_back_button()

        self.update_ui()

    # ===== BACK BUTTON =====

    def create_back_button(self):
        """Create the "← Back to Menu" button below the board."""
        self.back_btn_canvas = tk.Canvas(
            self,
            width=220,
            height=50,
            highlightthickness=0,
            bg=self.theme["bg"]
        )
        self.back_btn_canvas.pack(pady=10)

        x, y = 110, 25
        w, h = 180, 40

        color = self.theme["grid"]
        hover_color = self.theme["x"]

        rect = self.back_btn_canvas.create_rectangle(
            x - w//2, y - h//2,
            x + w//2, y + h//2,
            fill=color, outline=""
        )

        text = self.back_btn_canvas.create_text(
            x, y,
            text="← Back to Menu",
            fill="white",
            font=("Segoe UI", 11, "bold")
        )

        def on_enter(e):
            self.back_btn_canvas.itemconfig(rect, fill=hover_color)

        def on_leave(e):
            self.back_btn_canvas.itemconfig(rect, fill=color)

        def on_click(e):
            self.back_menu()

        for item in (rect, text):
            self.back_btn_canvas.tag_bind(item, "<Enter>", on_enter)
            self.back_btn_canvas.tag_bind(item, "<Leave>", on_leave)
            self.back_btn_canvas.tag_bind(item, "<Button-1>", on_click)

    # ===== BOARD RENDERING =====

    def draw(self):
        """Redraw the entire board: grid lines + all placed stones.

        PLAYER (1) → X mark (two diagonal lines)
        AI (-1)    → Oval (circle)
        Both are colored per the current theme.
        """
        self.canvas.delete("all")

        # Grid lines (BOARD_SIZE+1 lines in each direction)
        for i in range(BOARD_SIZE + 1):
            self.canvas.create_line(i * CELL_SIZE, 0, i * CELL_SIZE, 600,
                                    fill=self.theme["grid"])
            self.canvas.create_line(0, i * CELL_SIZE, 600, i * CELL_SIZE,
                                    fill=self.theme["grid"])

        # Stones
        pad = CELL_SIZE // 4
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                x1 = c * CELL_SIZE + pad
                y1 = r * CELL_SIZE + pad
                x2 = (c + 1) * CELL_SIZE - pad
                y2 = (r + 1) * CELL_SIZE - pad

                if self.board[r][c] == PLAYER:
                    # X shape: two crossing lines
                    self.canvas.create_line(x1, y1, x2, y2,
                                            fill=self.theme["x"], width=3)
                    self.canvas.create_line(x1, y2, x2, y1,
                                            fill=self.theme["x"], width=3)

                elif self.board[r][c] == AI:
                    # O shape: oval with outline
                    self.canvas.create_oval(x1, y1, x2, y2,
                                            outline=self.theme["o"], width=3)

    def update_ui(self):
        """Redraw and update the status label based on game state."""
        self.draw()
        if self.game_over:
            return
        if self.waiting_for_ai:
            self.status.config(text="AI is thinking...")
        else:
            self.status.config(text="Your Turn (X)")

    # ===== CLICK HANDLING =====

    def click(self, event):
        """Handle a mouse click on the board.

        Converts pixel coordinates to board coordinates, places the stone,
        checks for win/draw, and schedules the AI turn if the game continues.
        """
        if self.game_over or self.waiting_for_ai:
            return

        col = event.x // CELL_SIZE
        row = event.y // CELL_SIZE

        if make_move(self.board, row, col, PLAYER):
            self.update_ui()

            if check_winner(self.board, PLAYER):
                self.game_over = True
                self.update_ui()
                messagebox.showinfo("Game Over", "You Win!")
                return

            self.waiting_for_ai = True
            self.update_ui()
            # 300ms delay so the UI redraws the player's stone before AI computes
            self.after(300, self.ai_turn)

    def ai_turn(self):
        """Calculate and execute the AI move, then check for win/draw."""
        move = ai_move(self.board, self.difficulty)
        if move:
            r, c = move
            make_move(self.board, r, c, AI)

            if check_winner(self.board, AI):
                self.game_over = True
                self.waiting_for_ai = False
                self.update_ui()
                messagebox.showinfo("Game Over", "AI Wins!")
                return

        self.waiting_for_ai = False
        self.update_ui()

    def back_menu(self):
        """Return to the main menu."""
        self.controller.show_frame(MenuFrame)


# ================= RUN =================

if __name__ == "__main__":
    app = CaroApp()
    app.mainloop()
