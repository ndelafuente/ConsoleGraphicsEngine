import curses
from enum import IntEnum, StrEnum

from PngCodec import PngDecoder
from utils.integer import bound, stable_round
from utils.string import (
    delete_next_word,
    delete_prev_word,
    find_next_word,
    find_prev_word,
    str_delete,
    str_insert,
)

global DEBUG
DEBUG = False


class Key(IntEnum):
    NONE = -1
    CTRL_D = 4
    CTRL_X = 24
    TAB = 9  # CTRL + I
    ENTER = 10  # CTRL + J, CTRL + M
    ESC = 27
    CMD_DELETE = 21  # CTRL + U
    ALT_DELETE = 23  # CTRL + W
    DELETE = 127
    FN_DELETE = 330
    DOWN = 258
    UP = 259
    LEFT = 260
    RIGHT = 261
    CMD_LEFT = 1  # CTRL + A
    CMD_RIGHT = 5  # CTRL + E


class EscCode(StrEnum):
    SEQ_START = "["
    ALT_LEFT = "b"
    ALT_RIGHT = "f"
    FN_ALT_DELETE = "d"
    FN_CMD_DELETE = "3;9~"


SPRITE = PngDecoder("car.png")


def main(win: curses.window):
    global DEBUG
    win.clear()
    win.nodelay(True)
    curses.curs_set(0)  # hide the cursor
    curses.use_default_colors()
    curses.mousemask(curses.ALL_MOUSE_EVENTS)

    for color_i in range(1, curses.COLORS):
        curses.init_pair(color_i, color_i, color_i)

    color_i = 0
    j = 0
    canvas = VirtualCanvas(win)
    while True:
        ch = win.getch()
        if ch == ord('q'):
            return 0
        if ch == ord('f'):
            j = 0
        if ch == ord('d'):
            DEBUG = not DEBUG

        if ch == curses.KEY_MOUSE:
            win.clear()
            max_y, max_x = win.getmaxyx()

            if DEBUG:
                # Debugging
                canvas.safe_print(0, 0, str((x, y, bin(button), color_i)))
                debug_info = [
                    f"Max X, Y: {tuple(reversed(win.getmaxyx()))}",
                    f"Has Colors: {curses.has_colors()}",
                    f"Num Colors: {curses.COLORS}",
                    f"Can Change Color: {curses.can_change_color()}"
                ]
                for row, info in enumerate(debug_info, -len(debug_info)):
                    canvas.safe_print(row, 0, info)

                grid_x = max_x // 4
                grid_y = max_y // 2 - 5
                canvas.safe_print(grid_y, grid_x, " 123456789")
                for i in range(1, 9):
                    canvas.safe_print(grid_y+i, grid_x, str(i))
                color_i = 1

            _, x, y, _, button = curses.getmouse()
            canvas_x, canvas_y = canvas.virtualize(x, y)
            if button & curses.BUTTON1_RELEASED:
                pass
            elif button & curses.BUTTON1_PRESSED:
                pass
            elif button & curses.BUTTON1_CLICKED:
                canvas.draw_circle(canvas_x, canvas_y, j, curses.color_pair(color_i))
                j = (j + 1) % (min(max_x, max_y) // 2)
            elif button & curses.BUTTON1_DOUBLE_CLICKED:
                canvas.add_sprite(canvas_x, canvas_y, SPRITE)
            elif button & curses.BUTTON1_TRIPLE_CLICKED:
                win.clear()
                prompt = "Enter command to try: "
                curr_input = canvas.input(0, 0, prompt)
                if curr_input:
                    try:
                        res = eval(curr_input)
                        canvas.safe_print(2, 0, f'{curr_input} = {res}')
                    except BaseException as e:
                        canvas.safe_print(2, 0, repr(e))
                win.refresh()

            elif button & curses.REPORT_MOUSE_POSITION:
                canvas.draw_box(canvas_x, canvas_y, 3, 3, curses.color_pair(color_i))
                color_i = (color_i + 1) % curses.COLORS
            win.refresh()


class VirtualCanvas:
    def __init__(self, win: curses.window, x_scale=2, y_scale=1) -> None:
        self.screen = win
        self.x_scale = x_scale
        self.y_scale = y_scale
        self.p = 0
        self.update_screen_size()

    def update_screen_size(self):
        self.max_y, self.max_x = self.screen.getmaxyx()

    def virtualize(self, actual_x, actual_y):
        return actual_x / self.x_scale, actual_y / self.y_scale

    def color_virtual_pixel(self, x, y, color):
        if DEBUG:
            self.safe_print(self.p, 80, f"{x,y}")

        max_y, max_x = self.screen.getmaxyx()
        for n in range(self.x_scale):
            for m in range(self.y_scale):
                raw_x = (x * self.x_scale + n)
                raw_y = (y * self.y_scale + m)

                actual_x = stable_round(raw_x)
                actual_y = stable_round(raw_y)
                if actual_x >= 0 and actual_x < max_x and actual_y >= 0 and actual_y < max_y:
                    self.screen.chgat(actual_y, actual_x, 1, color)

                    if DEBUG:
                        self.safe_print(self.p, 100, f"{raw_x, raw_y}")
                        self.safe_print(self.p, 120, f"{actual_x, actual_x}")
                        self.p += 1

    def add_sprite(self, x, y, sprite: PngDecoder):
        color_palette = set(sprite.pixels.values())
        def c(v): return round((v / 255) * 1000)

        for i, color in enumerate(color_palette):
            r, g, b, a = color
            curses.init_color(20 + i, c(r), c(g), c(b))

        colors = {curses.color_content(color_code): color_code
                  for color_code in range(curses.COLORS)}
        for row, col in sprite.pixels:
            r, g, b, a = sprite.pixels[row, col]
            color_code = colors[c(r), c(g), c(b)]
            self.color_virtual_pixel(x + col, y + row, curses.color_pair(color_code))

    def safe_print(self, row: int, col: int, str: str, color=None):
        if row < 0:
            row += self.max_y
        if col < 0:
            col += self.max_x

        if row >= 0 and row < self.max_y and col >= 0 and col < self.max_x:
            if color is not None:
                self.screen.addstr(row, col, str, color)
            else:
                self.screen.addstr(row, col, str)

    def input(self, row, col, prompt):
        # Enter input mode
        curses.mousemask(0)
        curses.curs_set(1)
        curses.flushinp()

        curr_input = ""
        unrecognized = []
        input_start = len(prompt)
        self.safe_print(row, col, prompt)
        while True:
            cursor_y, cursor_x = self.screen.getyx()
            cursor_i = cursor_x - input_start
            input_end = input_start + len(curr_input)

            match self.screen.getch():
                case Key.ENTER:
                    break  # stop input loop

                case Key.CTRL_D | Key.CTRL_X:
                    exit()

                case Key.ESC:
                    # Handle escape characters
                    match chr(self.screen.getch()):
                        case EscCode.ALT_LEFT:
                            # Move cursor to the beginning of previous word
                            new_x = find_prev_word(curr_input, cursor_i)
                            self.screen.move(cursor_y, input_start + new_x)
                        case EscCode.ALT_RIGHT:
                            # Move cursor to the beginning of next word
                            new_x = find_next_word(curr_input, cursor_i)
                            self.screen.move(cursor_y, input_start + new_x)
                        case EscCode.FN_ALT_DELETE:
                            # Delete next word
                            self.safe_print(row, input_start, " " * len(curr_input))
                            curr_input, _ = delete_next_word(curr_input, cursor_i)
                            self.safe_print(row, input_start, curr_input)
                            self.screen.move(cursor_y, cursor_x)
                        case EscCode.SEQ_START if self._match_seq(EscCode.FN_CMD_DELETE):
                            # Delete from cursor to end of line
                            len_deleted = len(curr_input) - cursor_i
                            curr_input = curr_input[:cursor_i]
                            self.safe_print(row, cursor_x, " " * len_deleted)
                            self.screen.move(cursor_y, cursor_x)
                        case Key.ESC | Key.NONE:
                            # Cancel
                            curr_input = ""
                            break
                        case unknown:
                            unrecognized.append((Key.ESC, unknown))

                case Key.LEFT:
                    if cursor_x > input_start:
                        self.screen.move(cursor_y, cursor_x - 1)
                case Key.RIGHT:
                    if cursor_x < input_end:
                        self.screen.move(cursor_y, cursor_x + 1)
                case Key.CMD_LEFT:
                    self.screen.move(cursor_y, input_start)
                case Key.CMD_RIGHT:
                    self.screen.move(cursor_y, input_end)

                case Key.DELETE:
                    # Erase character before current position
                    if cursor_i > 0:
                        curr_input = str_delete(curr_input, cursor_i - 1)
                        self.screen.delch(cursor_y, cursor_x - 1)
                case Key.ALT_DELETE:
                    # Erase up to the start of the previous word
                    self.safe_print(row, input_start, " " * len(curr_input))
                    curr_input, del_start = delete_prev_word(curr_input, cursor_i)
                    self.safe_print(row, input_start, curr_input)
                    self.screen.move(cursor_y, input_start + del_start)
                case Key.CMD_DELETE:
                    # Completely erase input
                    self.safe_print(row, input_start, " " * len(curr_input))
                    self.screen.move(cursor_y, input_start)
                    curr_input = ""

                case c if c >= 32 and c < 127:
                    curr_input = str_insert(curr_input, chr(c), cursor_i)
                    self.screen.insch(cursor_y, cursor_x, chr(c))
                    self.screen.move(cursor_y, cursor_x + 1)

                case unknown if unknown >= 0:
                    unrecognized.append(unknown)

        # Restore normal mode
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.curs_set(0)
        curses.flushinp()

        if DEBUG and len(unrecognized) > 0:
            unrecognized = list(dict.fromkeys(unrecognized))
            self.safe_print(row + 1, col, f"Unrecognized: {unrecognized}")

        return curr_input

    def _match_seq(self, sequence: str):
        input = ''
        for _ in range(len(sequence)):
            input += chr(self.screen.getch())
            if not sequence.startswith(input):
                return False
        return sequence == input

    def devirtualize_x(self, virtual_x):
        actual_x = stable_round(virtual_x * self.x_scale)
        return bound(actual_x, max=self.max_x)

    def devirtualize_y(self, virtual_y):
        actual_y = stable_round(virtual_y * self.y_scale)
        return bound(actual_y, max=self.max_y)

    def draw_hline(self, x, y, length, color):
        max_y, max_x = self.screen.getmaxyx()
        approximate_pixel_count = self.devirtualize_x(length)
        x = self.devirtualize_x(x)
        y = self.devirtualize_y(y)
        if x >= 0 and x < max_x and y >= 0 and y < max_y:
            self.screen.chgat(y, x, approximate_pixel_count, color)

            if DEBUG:
                self.safe_print(self.p, 100, f"{x, y, approximate_pixel_count}")
                self.p += 1

    def draw_box(self, center_x, center_y, x_len, y_len, color):
        self.p = 0
        x = center_x - (x_len - 1) / 2
        y = center_y - (y_len - 1) / 2
        for m in range(stable_round(y_len)):
            self.draw_hline(x, y + m, x_len, color)

        if DEBUG:
            self.safe_print(1, 0, f"Box: {x_len} by {y_len}")
            self.safe_print(2, 0, f"Center: {center_x, center_y}")
            self.safe_print(3, 0, f"Start:  {x, y}")
            self.safe_print(4, 0, f"Lines drawn: {self.p}")

    def draw_circle(self, center_x, center_y, radius, color):
        """
        Adapted from Geeks for Geeks: "Mid-Point Circle Drawing Algorithm"
        https://geeksforgeeks.org/mid-point-circle-drawing-algorithm/
        """

        if DEBUG:
            self.safe_print(1, 0, f"Circle")
            self.safe_print(2, 0, f"Center: {center_x, center_y}")
            self.safe_print(3, 0, f"Radius: {radius}")
            self.p = 0

        x = radius
        y = 0

        # Printing the initial point the axes after translation
        if DEBUG:
            color = curses.color_pair(1)
        self.color_virtual_pixel(x + center_x, y + center_y, color)

        # When radius is zero only a single point will be printed
        if DEBUG:
            color = curses.color_pair(2)
        if (radius > 0):
            self.color_virtual_pixel(-x + center_x, -y + center_y, color)
            self.color_virtual_pixel(y + center_x, -x + center_y, color)
            self.color_virtual_pixel(-y + center_x, x + center_y, color)

        # Initialising the value of P
        P = 1 - radius

        while x > y:

            y += 1

            # Mid-point inside or on the perimeter
            if P <= 0:
                P = P + 2 * y + 1

            # Mid-point outside the perimeter
            else:
                x -= 1
                P = P + 2 * y - 2 * x + 1

            # All the perimeter points have already been printed
            if (x < y):
                break

            # Printing the generated point its reflection
            # in the other octants after translation
            if DEBUG:
                color = curses.color_pair(3)
            self.color_virtual_pixel(x + center_x, y + center_y, color)
            self.color_virtual_pixel(-x + center_x, y + center_y, color)
            self.color_virtual_pixel(x + center_x, -y + center_y, color)
            self.color_virtual_pixel(-x + center_x, -y + center_y, color)

            # If the generated point on the line x = y then
            # the perimeter points have already been printed
            if x != y:
                if DEBUG:
                    color = curses.color_pair(4)
                self.color_virtual_pixel(y + center_x, x + center_y, color)
                self.color_virtual_pixel(-y + center_x, x + center_y, color)
                self.color_virtual_pixel(y + center_x, -x + center_y, color)
                self.color_virtual_pixel(-y + center_x, -x + center_y, color)


if __name__ == "__main__":
    curses.wrapper(main)
