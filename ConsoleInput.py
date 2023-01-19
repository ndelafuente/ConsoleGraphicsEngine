from enum import Enum
from os import system, read

import atexit
import sys
import tty
import termios


class MouseCode(Enum):
    PRESS = 9
    PRESS_RELEASE = 1000
    HIGHLIGHT = 1001
    MOVEMENT = 1002
    ALL = 1003
    AS_UTF_8 = 1005
    AS_DECIMAL = 1006
    AS_DECIMAL_ALT = 1015


class ConsoleInput:
    def __init__(self) -> None:
        pass

    def enable_raw_mode(self):
        fd = sys.stdin.fileno()

        # Save terminal mode to restore at program exit
        old = termios.tcgetattr(fd)
        atexit.register(termios.tcsetattr, fd, termios.TCSADRAIN, old)

        tty.setraw(fd)

    # Mouse Reporting

    def enable_mouse(self, code: MouseCode):
        self._use_mouse_code(code)
        atexit.register(self.disable_mouse_reporting)

    def disable_mouse_reporting(self, code=MouseCode.ALL):
        self._use_mouse_code(code, disable=True)

    def _use_mouse_code(self, code: MouseCode, disable=False):
        command = f"printf '\e[?{code.value}'"
        command += 'l' if disable else 'h'
        system(command)


if __name__ == '__main__':
    ci = ConsoleInput()
    ci.enable_raw_mode()
    ci.enable_mouse(MouseCode.ALL)
    ci.enable_mouse(MouseCode.AS_DECIMAL)
    from datetime import datetime, timedelta
    start = datetime.now()
    input = ""
    while datetime.now() - start < timedelta(seconds=1):
        input += sys.stdin.read(1)
    sys.stdin.flush()
    print(input.encode())

