"""UI tests for Caro Game - uses pure mock tkinter classes (no real GUI)."""

from unittest.mock import patch, MagicMock
import pytest

from constants import PLAYER, AI, EASY, MEDIUM, HARD


# ===================== MOCK TKINTER CLASSES =====================

class MockTk:
    def __init__(self):
        self.title = MagicMock()
        self.geometry = MagicMock()
        self.resizable = MagicMock()
        self.configure = MagicMock()
        self.mainloop = MagicMock()

class MockFrame:
    _instances = []

    def __init__(self, parent=None, **kwargs):
        MockFrame._instances.append(self)
        self.parent = parent
        self.pack = MagicMock()
        self.place = MagicMock()
        self.tkraise = MagicMock()
        self.configure = MagicMock()
        self.config = MagicMock()
        self.after = MagicMock()

class MockCanvas:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.pack = MagicMock()
        self.create_line = MagicMock(return_value=1)
        self.create_rectangle = MagicMock(return_value=2)
        self.create_text = MagicMock(return_value=3)
        self.create_oval = MagicMock(return_value=4)
        self.delete = MagicMock()
        self.bind = MagicMock()
        self.tag_bind = MagicMock()
        self.itemconfig = MagicMock()
        self.configure = MagicMock()
        self.config = MagicMock()
        self.pack_forget = MagicMock()
        self.destroy = MagicMock()

class MockLabel:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.pack = MagicMock()
        self.config = MagicMock()
        self.configure = MagicMock()
        self.destroy = MagicMock()

class MockMessagebox:
    showinfo = MagicMock()


# ===================== PATCH TKINTER =====================

@pytest.fixture(autouse=True)
def _patch_tkinter():
    """Patch tkinter classes before each test."""
    tk_patcher = patch.dict("sys.modules", {
        "tkinter": MagicMock(
            Tk=MockTk,
            Frame=MockFrame,
            Canvas=MockCanvas,
            Label=MockLabel,
        )
    })
    tk_patcher.start()

    import ui
    # Replace tk.Frame with our mock so inheritance works
    ui.tk.Tk = MockTk
    ui.tk.Frame = MockFrame
    ui.tk.Canvas = MockCanvas
    ui.tk.Label = MockLabel
    ui.tk.Canvas.bind = lambda self, *a, **kw: None

    # Patch messagebox
    mb_patcher = patch("ui.messagebox", MockMessagebox)
    mb_patcher.start()

    MockFrame._instances.clear()

    yield

    mb_patcher.stop()
    tk_patcher.stop()


# ===================== CARO APP TESTS =====================

class TestCaroApp:
    def test_init_creates_window(self):
        import ui
        app = ui.CaroApp()
        app.title.assert_called_once_with("Caro Game Pro")
        app.geometry.assert_called_once_with("700x780")
        app.resizable.assert_called_once_with(False, False)

    def test_init_creates_two_frames(self):
        import ui
        app = ui.CaroApp()
        assert ui.MenuFrame in app.frames
        assert ui.GameFrame in app.frames

    def test_show_frame(self):
        import ui
        app = ui.CaroApp()
        mock_frame = app.frames[ui.GameFrame]
        app.show_frame(ui.GameFrame)
        mock_frame.tkraise.assert_called_once()

    def test_start_game_easy(self):
        import ui
        app = ui.CaroApp()
        mock_game_frame = app.frames[ui.GameFrame]
        mock_game_frame.start_new_game = MagicMock()
        app.start_game(EASY)
        mock_game_frame.start_new_game.assert_called_once_with(EASY)

    def test_start_game_hard(self):
        import ui
        app = ui.CaroApp()
        mock_game_frame = app.frames[ui.GameFrame]
        mock_game_frame.start_new_game = MagicMock()
        app.start_game(HARD)
        mock_game_frame.start_new_game.assert_called_once_with(HARD)


# ===================== MENU FRAME TESTS =====================

class TestMenuFrame:
    def test_init_creates_canvas(self):
        import ui
        menu = ui.MenuFrame(MagicMock(), MagicMock())
        assert hasattr(menu, 'canvas')

    def test_init_draws_title(self):
        import ui
        menu = ui.MenuFrame(MagicMock(), MagicMock())
        menu.canvas.create_text.assert_any_call(
            350, 120, text="CARO GAME", fill="white",
            font=("Segoe UI", 32, "bold")
        )
        menu.canvas.create_text.assert_any_call(
            350, 180, text="Select Difficulty", fill="#cccccc",
            font=("Segoe UI", 16)
        )

    def test_easy_button_color(self):
        import ui
        menu = ui.MenuFrame(MagicMock(), MagicMock())
        rect_calls = menu.canvas.create_rectangle.call_args_list
        fills = [kw.get("fill") for _, kw in rect_calls if kw.get("fill")]
        assert "#4CAF50" in fills

    def test_medium_button_color(self):
        import ui
        menu = ui.MenuFrame(MagicMock(), MagicMock())
        rect_calls = menu.canvas.create_rectangle.call_args_list
        fills = [kw.get("fill") for _, kw in rect_calls if kw.get("fill")]
        assert "#2196F3" in fills

    def test_hard_button_color(self):
        import ui
        menu = ui.MenuFrame(MagicMock(), MagicMock())
        rect_calls = menu.canvas.create_rectangle.call_args_list
        fills = [kw.get("fill") for _, kw in rect_calls if kw.get("fill")]
        assert "#f44336" in fills

    def test_easy_button_click_starts_game(self):
        import ui
        controller = MagicMock()
        menu = ui.MenuFrame(MagicMock(), controller)
        for args in menu.canvas.tag_bind.call_args_list:
            if args[0][1] == "<Button-1>":
                args[0][2](MagicMock())
        controller.start_game.assert_any_call(EASY)

    def test_lighten_method(self):
        import ui
        menu = ui.MenuFrame(MagicMock(), MagicMock())
        result = menu.lighten("#112233")
        assert result == "#394a5b"

    def test_lighten_clamps_at_255(self):
        import ui
        menu = ui.MenuFrame(MagicMock(), MagicMock())
        result = menu.lighten("#ffffff")
        assert result == "#ffffff"


# ===================== GAME FRAME TESTS =====================

class TestGameFrame:
    def test_init_sets_waiting_false(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        assert frame.waiting_for_ai is False

    def test_start_new_game_sets_difficulty(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        assert frame.difficulty == EASY

    def test_start_new_game_resets_state(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(MEDIUM)
        assert frame.game_over is False
        assert frame.waiting_for_ai is False
        assert frame.board is not None

    def test_click_game_over_ignored(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        frame.game_over = True
        event = MagicMock()
        event.x = 200
        event.y = 200
        frame.click(event)
        assert frame.waiting_for_ai is False

    def test_click_ai_thinking_ignored(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        frame.waiting_for_ai = True
        event = MagicMock()
        event.x = 200
        event.y = 200
        frame.click(event)
        assert frame.game_over is False

    def test_click_empty_cell_makes_move(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        event = MagicMock()
        event.x = 80
        event.y = 80
        frame.click(event)
        col = 80 // ui.CELL_SIZE
        row = 80 // ui.CELL_SIZE
        assert frame.board[row][col] == PLAYER

    def test_click_triggers_ai(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        event = MagicMock()
        event.x = 80
        event.y = 80
        frame.click(event)
        assert frame.waiting_for_ai is True

    def test_click_player_wins(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        for col in range(4):
            frame.board[7][col] = PLAYER
        event = MagicMock()
        event.x = 4 * ui.CELL_SIZE
        event.y = 7 * ui.CELL_SIZE
        MockMessagebox.showinfo.reset_mock()
        frame.click(event)
        assert frame.game_over is True
        MockMessagebox.showinfo.assert_called_with("Game Over", "You Win!")

    def test_ai_turn_normal(self):
        import ui
        with patch("ui.ai_move", return_value=(5, 5)):
            frame = ui.GameFrame(MagicMock(), MagicMock())
            frame.start_new_game(EASY)
            frame.ai_turn()
            assert frame.board[5][5] == AI
            assert frame.waiting_for_ai is False

    def test_ai_turn_ai_wins(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        for col in range(4):
            frame.board[7][col] = AI
        with patch("ui.ai_move", return_value=(7, 4)):
            MockMessagebox.showinfo.reset_mock()
            frame.ai_turn()
            assert frame.game_over is True
            assert frame.waiting_for_ai is False
            MockMessagebox.showinfo.assert_called_with("Game Over", "AI Wins!")

    def test_ai_turn_no_move(self):
        import ui
        with patch("ui.ai_move", return_value=None):
            frame = ui.GameFrame(MagicMock(), MagicMock())
            frame.start_new_game(EASY)
            frame.waiting_for_ai = True
            frame.ai_turn()
            assert frame.waiting_for_ai is False

    def test_back_menu(self):
        import ui
        controller = MagicMock()
        frame = ui.GameFrame(MagicMock(), controller)
        frame.back_menu()
        controller.show_frame.assert_called_once_with(ui.MenuFrame)

    def test_update_ui_player_turn(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        frame.waiting_for_ai = False
        frame.update_ui()
        frame.status.config.assert_called_with(text="Your Turn (X)")

    def test_update_ui_ai_thinking(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        frame.waiting_for_ai = True
        frame.update_ui()
        frame.status.config.assert_called_with(text="AI is thinking...")

    def test_update_ui_skips_when_game_over(self):
        import ui
        frame = ui.GameFrame(MagicMock(), MagicMock())
        frame.start_new_game(EASY)
        frame.status.config.reset_mock()
        frame.game_over = True
        frame.update_ui()
        frame.status.config.assert_not_called()
