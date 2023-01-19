import time
import curses
import math

global DEBUG
DEBUG = False


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
                pass
            elif button & curses.BUTTON1_TRIPLE_CLICKED:
                pass
            elif button & curses.REPORT_MOUSE_POSITION:
                canvas.draw_box(canvas_x, canvas_y, 3, 3, curses.color_pair(color_i))
                color_i = (color_i + 1) % curses.COLORS
            win.refresh()


def bound(number, min=0, max=None):
    if number < min:
        return min
    if max is not None and number > max:
        return max
    return number


def stable_round(number):
    integer_part = int(number)
    fractional_part = integer_part - number
    if fractional_part >= 0.5:
        return integer_part
    else:
        return integer_part + 1


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

    def safe_print(self, row: int, col: int, str: str):
        if row < 0:
            row += self.max_y
        if col < 0:
            col += self.max_x

        if row >= 0 and row < self.max_y and col >= 0 and col < self.max_x:
            self.screen.addstr(row, col, str)

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
                # self.safe_print(7, 0, f"{x, y, approximate_pixel_count}")
                self.p += approximate_pixel_count

    def draw_box(self, center_x, center_y, x_len, y_len, color):
        self.p = 0
        x = center_x - (x_len - self.x_scale) / 2
        y = center_y - (y_len - self.y_scale) / 2
        for m in range(stable_round(y_len)):
            self.draw_hline(x, y + m, x_len, color)

        if DEBUG:
            self.safe_print(1, 0, f"Box: {x_len} by {y_len}")
            self.safe_print(2, 0, f"Center: {center_x, center_y}")
            self.safe_print(3, 0, f"Start:  {x, y}")
            self.safe_print(4, 0, f"Pixels drawn: {self.p}")

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


curses.wrapper(main)
