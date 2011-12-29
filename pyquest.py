# -*- coding: utf-8 -*-
import curses
import signal
import sys
import time

import locale
locale.setlocale(locale.LC_ALL,"")


class Spawn(object):
    """MOB & Users"""

    def __init__(self, avatar, y, x):
        self.avatar = avatar
        self.y = y
        self.x = x
        self.zone = None

    def set_zone(self, zone):
        self.zone = zone

    def move_to(self, y, x):
        self.zone.unset_field(self.y, self.x)
        self.y = y
        self.x = x
        self.zone.set_field(y, x, self)


class Zone(object):
    """Keeps track of what's on the field. Does collision detection, etc."""

    def __init__(self, y, x, screen):
        self.y = y
        self.x = x
        self.screen = screen

        self.field = []
        for i in xrange(y):
            row = []
            for j in xrange(x):
                row.append(None)
            self.field.append(row)

        self.spawns = {}

    def add_spawn(self, spawn):
        """Should immediately render spawn on map."""
        spawn.set_zone(self)
        self.set_field(spawn.y, spawn.x, spawn)

    def unset_field(self, y, x):
        self.field[y][x] = None
        self.screen.update(y, x, ' ')

    def set_field(self, y, x, obj):
        self.field[y][x] = obj
        #self.spawns[spawn] = (spawn.y, spawn.x)
        self.screen.update(y, x, obj.avatar)



class Screen(object):
    """Abstraction to curses."""

    def __init__(self, window):
        self.window = window

    def update(self, y, x, ch):
        self.window.addstr(y, x, ch)


    """
    def mob_move(self, spawn, old_y, old_x):
        self.window.addch(old_y, old_x)
        self.window.addch(spawn.y, spawn.x, spawn.avatar)
    """


class UserControl(object):
    """Moves the character around the zone"""

    def __init__(self, mob):
        self.mob = mob

    def accept(self, ch):
        if ch in (curses.KEY_DOWN, curses.KEY_UP,
                  curses.KEY_LEFT, curses.KEY_RIGHT):
            self.move_cardinal(ch)

    def move_cardinal(self, key):
        y, x = old_y, old_x = self.mob.y, self.mob.x
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
        self.mob.move_to(y, x)



def main(window):
    curses.curs_set(0)
    curses.cbreak()
    window.nodelay(1)
    window.border(0)

    screen = Screen(window)
    zone = Zone(100, 100, screen)
    user = Spawn('@', 1, 1)
    control = UserControl(user)

    zone.add_spawn(user)

    while True:
        ch = window.getch()
        control.accept(ch)
        window.refresh()



try:
    curses.wrapper(main)
except KeyboardInterrupt:
    sys.exit(0)
