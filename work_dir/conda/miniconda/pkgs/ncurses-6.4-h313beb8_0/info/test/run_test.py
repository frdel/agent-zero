#  tests for ncurses-6.4-h313beb8_0 (this is a generated file);
print('===== testing package: ncurses-6.4-h313beb8_0 =====');
print('running run_test.py');
#  --- run_test.py (begin) ---
import curses
import sys

if __name__ == '__main__':
    if sys.stdout.isatty():
        screen = curses.initscr()
        try:
            curses.cbreak()
            pad = curses.newpad(10, 10)
            size = screen.getmaxyx()
            pad.refresh(0, 0, 0, 0, size[0] - 1, size[1] - 1)
        finally:
            curses.nocbreak()
            curses.endwin()
#  --- run_test.py (end) ---

print('===== ncurses-6.4-h313beb8_0 OK =====');
