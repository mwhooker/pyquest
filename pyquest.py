# -*- coding: utf-8 -*-
from __future__ import division
import curses
import curses.panel
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
        self.attack_rating = 1
        self.health_rating = 10
        self.armor_rating = 1
        self.damage_taken = 0
        self.regen_rate = 1 / 30
        self.level = 1

    def is_user(self):
        return False

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

    def attack(self, target=None):
        if not target:
            target = self.get_facing()
        if not target:
            return
        self.do_attack(target)

    def do_attack(self, opponent):
        base_damage = self.attack_rating * self.level
        mitigation = opponent.armor / 2
        opponent.take_damage(self, max(0, base_damage - mitigation))

    def take_damage(self, target, dmg):
        ChatBox.instance().add_message(
            "%s hits %s for %s damage" % (target.avatar, self.avatar, dmg)
        )
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
        # TODO: move to Zone?
        return [self.zone.get_field(*loc) for loc in self.circle_iter(radius)
                if self.zone.has_spawn(*loc)]
        
    def regenerate(self):
        # TODO
        if self.health_remaining == self.health_total:
            return

        regen = min(self.regen_rate, self.health_total - self.health_remaining)
        self.damage_taken -= regen

    def tick(self):
        """Must always be called by by subclasses."""
        self.regenerate()

class Player(Spawn):

    def __init__(self, *args, **kwargs):
        super(Player, self).__init__(*args, **kwargs)

        # a running total this chaacter has.
        self.experience = 0

    def is_user(self):
        return True

    def do_ding(self):
        ChatBox.instance().add_message("Ding! level %d" % self.level)
        self.level += 1

    def add_experience(self, exp):
        self.experience += exp

    # TODO:
    # you should be able to functionally figure out how much
    # exp is needed for next level,
    def experience_needed(self):
        return (((1 + self.level) / 2) * self.level) * (self.level + 14)

    def tick(self):
        super(Player, self).tick()
        if self.experience >= self.experience_needed():
            self.do_ding()
        if self.is_dead:
            sys.exit(0)

    def con(self, spawn):
        """[-1, 1], lower being easier, higher being harder, 0 being even. """
        delta = spawn.level - self.level
        if delta == 0:
            return 0
        return 1 / delta


class Mob(Spawn):

    def __init__(self, y, x, avatar='M'):
        super(Mob, self).__init__(y, x, avatar)

        self.hate = defaultdict(int)
        self.kos = True
        self.flees = False

    @property
    def exp(self):
        return self.level * 5

    def can_hit(self, target):
        return self.distance(target) == 1

    def take_damage(self, target, dmg):
        super(Mob, self).take_damage(target, dmg)
        if self.is_dead:
            target.add_experience(self.exp)
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
        # TODO: doesn't avoid obstacles.
        if self.can_hit(target):
            self.attack(target)
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
        super(Mob, self).tick()

        # attack or flee
        if self.flees and \
           self.health_total * 0.1 >= self.health_remaining:
            self.flee()
        elif len(self.hate):
            self.chase(
                max(self.hate.items(), key=lambda x: x[1])[0]
            )
        elif self.kos:
            targets = self.targets_in_radius(3)
            targets = [t for t in targets if t.is_user()]
            if len(targets):
                self.hate[self.nearest_target(targets)] = 2

        forget = []
        for spawn in self.hate:
            # slowely forget hate
            if self.distance(spawn) > 5:
                self.hate[spawn] *= 0.99

            # remove distant targets on hate list
            if self.distance(spawn) > 20:
                forget.append(spawn)

            # remove spawns with no hate left
            if self.hate[spawn] < 1:
                forget.append(spawn)

            if spawn.is_dead:
                forget.append(spawn)

        for spawn in forget:
            del self.hate[spawn]




class Zone(object):
    """Keeps track of what's on the field. Does collision detection, etc."""

    def __init__(self, y, x, screen):
        self.y = y
        self.x = x
        self.screen = screen
        self.player = None

        self.field = []
        for i in xrange(y):
            row = []
            for j in xrange(x):
                row.append(None)
            self.field.append(row)

        self.spawns = {}

    def set_player(self, player):
        if not isinstance(player, Player):
            raise TypeError
        self.player = player
        self.add_spawn(player)

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

        if spawn is not self.player:
            con = self.player.con(spawn)
        else:
            con = None
        self.screen.update(y, x, spawn.avatar, con)

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

    def route(self, y1, x1, y2, x2):
        # TODO
        pass

    @staticmethod
    def distance(y1, x1, y2, x2):
        delta_y = abs(y1 - y2)
        delta_x = abs(x1 - x2)
        return math.sqrt(pow(delta_y, 2) + pow(delta_x, 2))

    def tick(self):
        for spawn in self.spawns.keys():
            # set con if not player
            if spawn is not self.player:
                self.screen.update_con(
                    spawn.y, spawn.x,
                    self.player.con(spawn)
                )

            spawn.tick()
            if spawn.is_dead:
                self.remove_spawn(spawn)
                continue



class Screen(object):
    """Abstraction to curses."""

    def __init__(self, window):
        self.window = window
    
    """
    level:
        trivial: green
        undecided: blue
        dangerous: yellow
        impossible: red
        boss:   A_BOLD ?
    """

    def _rating_to_color(self, rating):
        blue = 1
        cyan = 2
        green = 3
        magenta = 4
        red = 5
        white = 6
        yellow = 7

        if not rating:
            return white
        elif rating < -0.25:
            return blue
        elif rating < -0.5:
            return cyan
        elif rating < 0:
            return green
        elif rating < 0.25:
            return magenta
        elif rating < 0.75:
            return red
        elif rating >= 0.75:
            return yellow

    def update_con(self, y, x, rating):
        color = curses.color_pair(self._rating_to_color(rating))
        self.window.chgat(y, x, 1, color)

    def update(self, y, x, ch, rating=None):
        color = curses.color_pair(self._rating_to_color(rating))
        self.window.addch(y, x, ch[0], color)


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
            self.spawn.facing = DIRECTIONS['down']
        elif key == curses.KEY_UP:
            y -= 1
            self.spawn.facing = DIRECTIONS['up']
        elif key == curses.KEY_LEFT:
            x -= 1
            self.spawn.facing = DIRECTIONS['left']
        elif key == curses.KEY_RIGHT:
            x += 1
            self.spawn.facing = DIRECTIONS['right']
        else:
            return
        self.spawn.move_to(y, x)


class ChatBox(object):

    def __init__(self, panel, hlines, vlines):
        self.panel = panel
        self.hlines = hlines
        self.vlines = vlines
        self.window = panel.window()

        self.panel.show()
        self.window.border(0)
        self.messages = []

    def add_message(self, message):
        self.messages.append(message)
        self.refresh()

    def refresh(self):
        for i, msg in enumerate(self.messages[-(self.hlines - 2):]):
            self.window.addnstr(i + 1, 1, msg, self.vlines)

        self.window.refresh()

    @staticmethod
    def instance():
        return ChatBox._instance


def init_colors():

    colors = (
        curses.COLOR_BLACK,
        curses.COLOR_BLUE,
        curses.COLOR_CYAN,
        curses.COLOR_GREEN,
        curses.COLOR_MAGENTA,
        curses.COLOR_RED,
        curses.COLOR_WHITE,
        curses.COLOR_YELLOW
    )

    for i, color in enumerate(colors):
        curses.init_pair(i, color, -1)



def main(window):
    curses.curs_set(0)
    curses.cbreak()
    curses.use_default_colors()
    assert curses.has_colors()
    window.nodelay(1)
    window.border(0)
    display_win = window.subwin(45, 100, 0, 0)

    init_colors()

    chat_win = window.subwin(20, 80, 0, 101)
    chat_panel = curses.panel.new_panel(chat_win)
    chatbox = ChatBox(chat_panel, 20, 80)
    ChatBox._instance = chatbox

    screen = Screen(display_win)
    zone = Zone(100, 100, screen)
    user = Player(1, 1, '@')
    user.level = 5
    zone.set_player(user)

    for i in xrange(1, 11):
        mob = Mob(i+1, 10, avatar=str(i))
        mob.level = 1
        zone.add_spawn(mob)

    control = UserControl(user)

    last_tick = 0
    while True:
        ch = window.getch()
        curses.flushinp()
        if ch > 0:
            control.accept(ch)

        if time.time() - last_tick >= (1 / 5):
            zone.tick()
            last_tick = time.time()

        display_win.refresh()
        time.sleep(1 / 60)



try:
    curses.wrapper(main)
except KeyboardInterrupt:
    sys.exit(0)
