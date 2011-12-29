import curses
import signal
import sys
import time


DIRECTIONS = (curses.KEY_DOWN, curses.KEY_UP, curses.KEY_LEFT, curses.KEY_RIGHT)


class Character(object):

    def __init__(self, avatar, y, x):
        self.avatar = avatar
        self.y = y
        self.x = x
        self.obstructing = None


    def move_cardinal(self, key, screen, units=1):
        y, x = old_y, old_x = self.y, self.x
        if key == curses.KEY_DOWN:
            y += 1
        elif key == curses.KEY_UP:
            y -= 1
        elif key == curses.KEY_LEFT:
            x -= 1
        elif key == curses.KEY_RIGHT:
            x += 1
        else:
            return
        self.y, self.x = y, x
        self.obstructing = screen.mob_move(self, old_y, old_x, self.obstructing)


class Zone(object):

    def __init__(self):
        pass

class Screen(object):

    def __init__(self, window):
        self.window = window

    def mob_move(self, spawn, old_y, old_x, obstructing):
        will_obstruct = self.window.getch(spawn.y, spawn.x) 
        """
        if obstructing:
            self.window.addch(old_y, old_x, obstructing)
        """
        self.window.addch(spawn.y, spawn.x, spawn.avatar)
        return will_obstruct


def main(window):
    curses.curs_set(0)
    window.nodelay(1)
    window.border(0)

    screen = Screen(window)

    user = Character('@', 1, 1)

    while True:
        ch = window.getch()
        if ch in DIRECTIONS:
            user.move_cardinal(ch, screen)

            

try:
    curses.wrapper(main)
except KeyboardInterrupt:
    sys.exit(0)
