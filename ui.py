import tkinter as tk
from tkinter import messagebox
from constants import BOARD_SIZE, PLAYER, AI, EASY, MEDIUM, HARD
from board import create_board, make_move
from rules import check_winner, is_board_full
from ai import ai_move

CELL_SIZE = 600 // BOARD_SIZE

THEMES = {
    EASY: {"bg": "#1f2f1f", "board": "#2e4d2e", "grid": "#88cc88", "x": "#00ff88", "o": "#ffffff"},
    MEDIUM: {"bg": "#1e1e2f", "board": "#2b2b3c", "grid": "#6666aa", "x": "#4da6ff", "o": "#ffffff"},
    HARD: {"bg": "#2a1a1a", "board": "#3b1f1f", "grid": "#ff5555", "x": "#ff4d4d", "o": "#ffffff"}
}

# ================= APP =================
class CaroApp(tk.Tk):
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
        self.frames[frame_class].tkraise()

    def start_game(self, difficulty):
        self.frames[GameFrame].start_new_game(difficulty)
        self.show_frame(GameFrame)


# ================= MENU =================
class MenuFrame(tk.Frame):
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
        for i in range(800):
            r = int(20 + i * 0.05)
            g = 20
            b = int(40 + i * 0.1)
            color = f'#{r:02x}{g:02x}{b:02x}'
            self.canvas.create_line(0, i, 700, i, fill=color)

    def lighten(self, color):
        color = color.lstrip('#')
        r, g, b = [int(color[i:i+2], 16) for i in (0, 2, 4)]
        r = min(255, r + 40)
        g = min(255, g + 40)
        b = min(255, b + 40)
        return f'#{r:02x}{g:02x}{b:02x}'

    def create_button(self, x, y, text, value, color):
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


# ================= GAME =================
class GameFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.canvas = tk.Canvas(self, width=600, height=600, highlightthickness=0)
        self.canvas.pack(pady=10)

        self.status = tk.Label(self, font=("Segoe UI", 12))
        self.status.pack()

        self.back_btn_canvas = None  # để recreate mỗi game

        self.canvas.bind("<Button-1>", self.click)

    def start_new_game(self, difficulty):
        self.difficulty = difficulty
        self.theme = THEMES[difficulty]

        self.board = create_board()
        self.game_over = False

        self.configure(bg=self.theme["bg"])
        self.canvas.config(bg=self.theme["board"])
        self.status.config(bg=self.theme["bg"], fg="white")

        # tạo lại nút back
        if self.back_btn_canvas:
            self.back_btn_canvas.destroy()
        self.create_back_button()

        self.update_ui()

    # ===== BACK BUTTON PRO =====
    def create_back_button(self):
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

    # ===== DRAW =====
    def draw(self):
        self.canvas.delete("all")

        for i in range(BOARD_SIZE + 1):
            self.canvas.create_line(i * CELL_SIZE, 0, i * CELL_SIZE, 600,
                                    fill=self.theme["grid"])
            self.canvas.create_line(0, i * CELL_SIZE, 600, i * CELL_SIZE,
                                    fill=self.theme["grid"])

        pad = CELL_SIZE // 4
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                x1 = c * CELL_SIZE + pad
                y1 = r * CELL_SIZE + pad
                x2 = (c + 1) * CELL_SIZE - pad
                y2 = (r + 1) * CELL_SIZE - pad

                if self.board[r][c] == PLAYER:
                    self.canvas.create_line(x1, y1, x2, y2,
                                            fill=self.theme["x"], width=3)
                    self.canvas.create_line(x1, y2, x2, y1,
                                            fill=self.theme["x"], width=3)

                elif self.board[r][c] == AI:
                    self.canvas.create_oval(x1, y1, x2, y2,
                                            outline=self.theme["o"], width=3)

    def update_ui(self):
        self.draw()
        if not self.game_over:
            self.status.config(text="Your Turn (X)")

    def click(self, event):
        if self.game_over:
            return

        col = event.x // CELL_SIZE
        row = event.y // CELL_SIZE

        if make_move(self.board, row, col, PLAYER):
            self.update_ui()

            if check_winner(self.board, PLAYER):
                self.game_over = True
                messagebox.showinfo("Game Over", "You Win!")
                return

            self.after(300, self.ai_turn)

    def ai_turn(self):
        move = ai_move(self.board, self.difficulty)
        if move:
            r, c = move
            make_move(self.board, r, c, AI)
            self.update_ui()

            if check_winner(self.board, AI):
                self.game_over = True
                messagebox.showinfo("Game Over", "AI Wins!")

    def back_menu(self):
        self.controller.show_frame(MenuFrame)


# ================= RUN =================
if __name__ == "__main__":
    app = CaroApp()
    app.mainloop()