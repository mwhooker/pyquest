# -*- coding: utf-8 -*-
from __future__ import division
import curses
import locale
import math
import random
import signal
import sys
import time

from collections import defaultdict


locale.setlocale(locale.LC_ALL,"")

DIRECTIONS = {
    'up': (-1, 0),
    'right': (0, 1),
    'down': (1, 0),
    'left': (0, -1)
}



class Spawn(object):
    """MOB & Users"""

    def __init__(self, y, x, avatar):
        self.y = y
        self.x = x
        self.avatar = avatar
        self.zone = None
        self.facing = DIRECTIONS['right']
        self.level = 1
        self.attack_rating = 1
        self.health_rating = 10
        self.armor_rating = 1
        self.damage_taken = 0

    @property
    def armor(self):
        return self.armor_rating * self.level

    @property
    def health_remaining(self):
        return self.health_total - self.damage_taken

    @property
    def health_total(self):
        return self.health_rating * self.level
    
    @property
    def is_dead(self):
        return self.health_remaining < 1

    def can_hit(self, target):
        return self.get_facing() == target

    def get_facing(self):
        target_y = self.y + self.facing[0]
        target_x = self.x + self.facing[1]
        return self.zone.get_field(target_y, target_x)

    def attack(self):
        target = self.get_facing()
        if not target:
            return

        self.do_attack(target)


    def do_attack(self, opponent):
        base_damage = self.attack_rating * self.level
        mitigation = opponent.armor / 2
        opponent.take_damage(self, base_damage - mitigation)

    def take_damage(self, target, dmg):
        self.damage_taken += dmg

    def set_zone(self, zone):
        self.zone = zone

    def move_to(self, y, x):
        self.zone.move_spawn(self, y, x)

    def nearest_target(self, spawns):
        enemies = [(spawn, spawn.x + spawn.y) for spawn in spawns]
        return min(enemies, key=lambda x: x[1])[0]
    
    def distance(self, target):
        return self.zone.distance(self.y, self.x, target.y, target.x)

    def circle_iter(self, r):
        """
        Iterator of coords in circle of r radius around self.

        TODO: not circular.
        """
        for y in xrange(self.y - r, self.y + r + 1):
            for x in xrange(self.x - r, self.x + r + 1):
                if (y, x) != (self.y, self.x):
                    yield (y, x)

    def targets_in_radius(self, radius):
        return [self.zone.get_field(*loc) for loc in self.circle_iter(radius)
                if self.zone.has_spawn(*loc)]
        

    def tick(self):
        pass

class Player(Spawn):

    def tick(self):
        if self.is_dead:
            sys.exit(0)


class Mob(Spawn):

    def __init__(self, y, x, avatar='M'):
        super(Mob, self).__init__(y, x, avatar)

        self.hate = defaultdict(int)
        self.kos = True

    def take_damage(self, target, dmg):
        super(Mob, self).take_damage(target, dmg)
        self.hate[target] += dmg

    def flee(self):
        target = self.nearest_target(self.hate)
        delta_y = self.y - target.y
        delta_x = self.x - target.x
        if abs(delta_x) > abs(delta_y):
            new_x = self.x + (1 if delta_x > 0 else -1)
            self.move_to(self.y, new_x)
        else:
            new_y = self.y + (1 if delta_y > 0 else -1)
            self.move_to(new_y, self.x)

    def chase(self, target):
        if self.can_hit(target):
            self.attack()
        else:
            delta_y = self.y - target.y
            delta_x = self.x - target.x
            if abs(delta_x) > abs(delta_y):
                new_x = self.x + (-1 if delta_x > 0 else 1)
                self.move_to(self.y, new_x)
            else:
                new_y = self.y + (-1 if delta_y > 0 else 1)
                self.move_to(new_y, self.x)


    def tick(self):
        if self.health_total * 0.1 >= self.health_remaining:
            self.flee()
        elif len(self.hate):
            self.chase(
                max(self.hate.items(), key=lambda x: x[1])[0]
            )
        elif self.kos:
            targets = self.targets_in_radius(3)
            if len(targets):
                self.hate[self.nearest_target(targets)] = 2

        # slowely forget hate
        for spawn in self.hate:
            if self.distance(spawn) > 5:
                self.hate[spawn] *= 0.99
        # remove distant targets on hate list
        forget = [spawn for spawn in self.hate
                         if self.distance(spawn) > 20]
        # remove spawns with no hate left
        forget.extend(spawn for spawn in self.hate
                             if self.hate[spawn] < 1)
        for spawn in forget:
            del self.hate[spawn]




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
        cur = self.field[y][x]
        self.field[y][x] = None
        if cur in self.spawns:
            del self.spawns[cur]
        self.screen.update(y, x, ' ')

    def is_occupied(self, y, x):
        return bool(self.field[y][x])
    
    def has_spawn(self, y, x):
        return isinstance(self.field[y][x], Spawn)

    def set_field(self, y, x, spawn):
        self.field[y][x] = spawn
        self.spawns[spawn] = (spawn.y, spawn.x)
        self.screen.update(y, x, spawn.avatar)

    def get_field(self, y, x):
        return self.field[y][x]

    def move_spawn(self, spawn, y, x):
        if self.is_occupied(y, x):
            return

        self.unset_field(spawn.y, spawn.x)
        spawn.y = y
        spawn.x = x
        self.set_field(y, x, spawn)

    def remove_spawn(self, spawn):
        self.unset_field(spawn.y, spawn.x)

    @staticmethod
    def distance(y1, x1, y2, x2):
        delta_y = abs(y1 - y2)
        delta_x = abs(x1 - x2)
        return math.sqrt(pow(delta_y, 2) + pow(delta_x, 2))

    def tick(self):
        for spawn in self.spawns.keys():
            spawn.tick()
            if spawn.is_dead:
                self.remove_spawn(spawn)
                continue



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

    def __init__(self, spawn):
        self.spawn = spawn

    def accept(self, ch):
        if ch in (curses.KEY_DOWN, curses.KEY_UP,
                  curses.KEY_LEFT, curses.KEY_RIGHT):
            self.move_cardinal(ch)
        elif ch == ord('a'):
            self.spawn.attack()

    def move_cardinal(self, key):
        y, x = old_y, old_x = self.spawn.y, self.spawn.x
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
        self.spawn.move_to(y, x)



def main(window):
    curses.curs_set(0)
    curses.cbreak()
    window.nodelay(1)
    window.border(0)

    screen = Screen(window)
    zone = Zone(100, 100, screen)
    user = Player(1, 1, '@')
    mob = Mob(10, 10)
    control = UserControl(user)

    zone.add_spawn(user)
    zone.add_spawn(mob)

    last_tick = 0
    while True:
        ch = window.getch()
        curses.flushinp()
        if ch > 0:
            control.accept(ch)

        if time.time() - last_tick >= (1 / 5):
            zone.tick()
            last_tick = time.time()

        window.refresh()
        time.sleep(1 / 60)



try:
    curses.wrapper(main)
except KeyboardInterrupt:
    sys.exit(0)
