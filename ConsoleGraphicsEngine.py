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

    for i in range(1, curses.COLORS):
        curses.init_pair(i, i, i)

    i = 0
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

        if DEBUG:
            # Debugging
            win.clear()
            win.addstr(0, 0, f"max x,y: {tuple(reversed(win.getmaxyx()))}")
            win.addstr(1, 0, f"has_colors: {curses.has_colors()}")
            win.addstr(2, 0, f"can_change_color: {curses.can_change_color()}")
            win.addstr(3, 0, f"has_extended_color_support: "
                       f"{curses.has_extended_color_support()}")
            time.sleep(0.05)
            continue

        if ch == curses.KEY_MOUSE:
            win.clear()
            _, x, y, _, button = curses.getmouse()
            canvas_x, canvas_y = canvas.virtualize(x, y)
            win.addstr(0, 0, str((x, y, bin(button), i)))
            if button & curses.BUTTON1_RELEASED:
                pass
            elif button & curses.BUTTON1_PRESSED:
                pass
            elif button & curses.BUTTON1_CLICKED:
                canvas.draw_circle(canvas_x, canvas_y, j)
                j = (j + 1) % 9
            elif button & curses.BUTTON1_DOUBLE_CLICKED:
                pass
            elif button & curses.BUTTON1_TRIPLE_CLICKED:
                pass
            elif button & curses.REPORT_MOUSE_POSITION:
                canvas.draw_box(canvas_x, canvas_y, 1.5, 1, curses.color_pair(i))
                i = (i + 1) % curses.COLORS
            win.refresh()


def safe_round(number):
    sign = 1 if number >= 0 else -1
    number = abs(number)
    fractional_part = int(number) - number
    if fractional_part < 0.5:
        return int(number)
    else:
        return int(number) + 1


class VirtualCanvas:
    def __init__(self, win: curses.window, x_scale=2, y_scale=1) -> None:
        self.screen = win
        self.x_scale = x_scale
        self.y_scale = y_scale
        self.p = 0
        self.update_screen_size()

    def update_screen_size(self):
        max_y, max_x = self.screen.getmaxyx()
        self.max_x = max_x // self.x_scale
        self.max_y = max_y // self.y_scale

    def virtualize(self, actual_x, actual_y):
        return actual_x / self.x_scale, actual_y / self.y_scale

    def color_pixel(self, x, y, color):
        max_y, max_x = self.screen.getmaxyx()
        self.screen.addstr(self.p, 80, f"{x,y}")

        for n in range(self.x_scale):
            for m in range(self.y_scale):
                raw_x = (x * self.x_scale + n)
                raw_y = (y * self.y_scale + m)

                actual_x = safe_round(raw_x)
                actual_y = safe_round(raw_y)
                if actual_x >= 0 and actual_x < max_x and actual_y >= 0 and actual_y < max_y:
                    self.screen.chgat(actual_y, actual_x, 1, color)

                    self.screen.addstr(self.p, 100, f"{raw_x, raw_y}")
                    self.screen.addstr(self.p, 120, f"{actual_x, actual_y}")
                    self.p += 1

    def draw_hline(self, start_x, y, length, color):

        x = start_x
        end = start_x + length
        step = 1 / self.x_scale
        while x < end:
            self.color_pixel(x, y, color)
            x += step

        # for n in range(round(length)):
        #     # n /= self.x_scale
        #     self.color_pixel(start_x + n, y, color)

    def draw_box(self, center_x, center_y, x_len, y_len, color):
        self.p = 0
        x = center_x - (x_len - 1) / 2
        y = center_y - (y_len - 1) / 2
        self.screen.addstr(1, 0, f"Center: {center_x, center_y}")
        self.screen.addstr(2, 0, f"Start:  {x, y}")
        for m in range(round(y_len)):
            self.draw_hline(x, y + m, x_len, color)
        self.screen.addstr(3, 0, f"Pixels drawn: {self.p}")
        self.screen.addstr(4, 0, "0123456789")

    def draw_circle(self, center_x, center_y, radius):
        self.p = 0
        x = radius
        y = 0
        self.screen.clear()
        color = curses.color_pair(1)
        # Printing the initial point the
        # axes after translation
        self.color_pixel(x + center_x, y + center_y, color)

        # When radius is zero only a single point will be printed
        if (radius > 0):
            color = curses.color_pair(2)
            self.color_pixel(-x + center_x, -y + center_y, color)
            self.color_pixel(y + center_x, -x + center_y, color)
            self.color_pixel(-y + center_x, x + center_y, color)

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

            # All the perimeter points have
            # already been printed
            if (x < y):
                break

            # Printing the generated point its reflection
            # in the other octants after translation
            color = curses.color_pair(3)
            self.color_pixel(x + center_x, y + center_y, color)
            self.color_pixel(-x + center_x, y + center_y, color)
            self.color_pixel(x + center_x, -y + center_y, color)
            self.color_pixel(-x + center_x, -y + center_y, color)

            # If the generated point on the line x = y then
            # the perimeter points have already been printed
            if x != y:
                color = curses.color_pair(4)
                self.color_pixel(y + center_x, x + center_y, color)
                self.color_pixel(-y + center_x, x + center_y, color)
                self.color_pixel(y + center_x, -x + center_y, color)
                self.color_pixel(-y + center_x, -x + center_y, color)

        self.screen.refresh()


curses.wrapper(main)
