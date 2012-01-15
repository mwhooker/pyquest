# -*- coding: utf-8 -*-
from __future__ import division
import curses
import curses.panel
import locale
import logging
import math
import random
import signal
import sys
import time
import types

from terrain import fill
from collections import defaultdict, namedtuple
from sched import scheduler


logging.basicConfig(filename='debug.log',level=logging.DEBUG)

locale.setlocale(locale.LC_ALL,"")

DIRECTIONS = {
    'up': (-1, 0),
    'right': (0, 1),
    'down': (1, 0),
    'left': (0, -1)
}


class UserControl(object):
    """Moves the character around the zone"""

    def __init__(self, spawn):
        self.spawn = spawn

    def accept(self, ch):
        if ch in (curses.KEY_DOWN, curses.KEY_UP,
                  curses.KEY_LEFT, curses.KEY_RIGHT):
            self.move_cardinal(ch)
        elif ch == ord('a'):
            self.spawn.attack()

    def move_cardinal(self, key):
        self.spawn.move_cardinal({
            curses.KEY_DOWN: 'down',
            curses.KEY_UP: 'up',
            curses.KEY_LEFT: 'left',
            curses.KEY_RIGHT: 'right'
        }[key])

