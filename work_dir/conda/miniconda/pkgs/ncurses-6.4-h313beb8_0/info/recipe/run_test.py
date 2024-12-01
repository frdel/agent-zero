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
