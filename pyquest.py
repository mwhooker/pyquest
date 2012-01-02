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

from collections import defaultdict, namedtuple


logging.basicConfig(filename='debug.log',level=logging.DEBUG)

locale.setlocale(locale.LC_ALL,"")

DIRECTIONS = {
    'up': (-1, 0),
    'right': (0, 1),
    'down': (1, 0),
    'left': (0, -1)
}


class Spawn(object):
    """MOB & Users"""

    def __init__(self, y, x, avatar, chat):
        logging.debug("spawning %s" % avatar)
        self.y = y
        self.x = x
        self.avatar = avatar
        self.chat = chat
        self.zone = None
        self.facing = DIRECTIONS['right']
        self.attack_rating = 2
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
        self.chat.add_message("mit: %s, base: %s" % (mitigation, base_damage))
        opponent.take_damage(self, max(0, base_damage - mitigation))

    def take_damage(self, target, dmg):
        self.chat.add_message(
            "%s hits %s for %s damage" % (target.avatar, self.avatar, dmg)
        )
        self.damage_taken += dmg

    def set_zone(self, zone):
        self.zone = zone

    def move_to(self, y, x):
        self.zone.move_spawn(self, y, x)

    # distance methods. Do these belong here, or in zone?

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
        self.level += 1
        self.chat.add_message("Ding! level %d" % self.level)

    def add_experience(self, exp):
        self.experience += exp

    @property
    def experience_needed(self):
        return (((1 + self.level) / 2) * self.level) * (self.level + 14)

    def tick(self):
        super(Player, self).tick()
        if self.experience >= self.experience_needed:
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

    def __init__(self, y, x, avatar='M', *args, **kwargs):
        super(Mob, self).__init__(y, x, avatar, *args, **kwargs)

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

        self.screen.update(y, x, spawn)

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

            spawn.tick()
            if spawn.is_dead:
                self.remove_spawn(spawn)
                continue

            self.screen.update(spawn.y, spawn.x, spawn)



class Screen(object):
    """Abstraction to curses."""

    def __init__(self, window, player):
        self.window = window
        self.player = player
    
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

    def update(self, y, x, cell):
        # TODO: going to have to abstract the cell object.
        # zone will need to keep track of terrain cells & spawn cells
        if isinstance(cell, Spawn):
            con = self.player.con(cell)
            color = curses.color_pair(self._rating_to_color(con))
            self.window.addch(y, x, cell.avatar[0], color)
        elif isinstance(cell, types.StringTypes):
            self.window.addch(y, x, cell[0])
        else:
            raise Exception("unrecognized type %s of cell" % type(cell))


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
        self.hlines = hlines - 2
        self.vlines = vlines - 2
        self.window = panel.window()

        self.panel.show()
        self.window.border(0)
        self.messages = []

    def add_message(self, msg):
        self.messages.append(msg)
        self.refresh()

    def refresh(self):
        for i, msg in enumerate(self.messages[-self.hlines:]):
            self.window.addnstr(i + 1, 1,
                                msg.ljust(self.vlines, ' '),
                                self.vlines)

        self.window.refresh()

class StatBox(object):
    """

    needs to display:
        cur/total health
        level
        exp/to_next_level
    """

    def __init__(self, panel, hlines, vlines, player):
        self.panel = panel
        self.hlines = hlines - 2
        self.vlines = vlines - 2
        self.player = player

        self.window = panel.window()

        self.panel.show()
        self.window.border(0)

    def tick(self):
        msgs = [
            "health: %d/%d" % (
                self.player.health_remaining,
                self.player.health_total
            ),
            "level: %d" % self.player.level,
            "exp: %d/%d" % (
                self.player.experience,
                self.player.experience_needed
            )
        ]

        for i, msg in enumerate(msgs):
            self.window.addnstr(i + 1, 1,
                                msg.ljust(self.vlines, ' '),
                                self.vlines)

        self.window.refresh()



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

    stat_win = window.subwin(20, 80, 20, 101)
    stat_panel = curses.panel.new_panel(stat_win)

    user = Player(1, 1, '@', chatbox)
    user.level = 2

    screen = Screen(display_win, user)
    zone = Zone(100, 100, screen)
    zone.add_spawn(user)

    statbox = StatBox(stat_panel, 20, 80, user)

    for i in xrange(1, 11):
        mob = Mob(i+1, 10, avatar=str(i), chat=chatbox)
        mob.level = 1
        zone.add_spawn(mob)

    control = UserControl(user)

    fps = Counter()

    def loop():
        ch = window.getch()
        curses.flushinp()
        if ch > 0:
            control.accept(ch)
        zone.tick()
        statbox.tick()
        fps.inc()
        display_win.refresh()

    target_fps = 1 / 60

    schedule = Scheduler()
    schedule.repeat(loop, target_fps)
    schedule.repeat(
        lambda: logging.info("Main loop operating at %f fps" % fps.flush()),
        1
    )


    while True:
        schedule.notify()
        next_event = schedule.next_event() - time.time()
        if next_event >= 0:
            time.sleep(next_event)
        else:
            logging.info("can't keep up. %s behind" % next_event)


class Counter(object):

    def __init__(self):
        self.count = 0

    def inc(self):
        self.count += 1

    def flush(self):
        tmp = self.count
        self.count = 0
        return tmp

class Tick(object):

    def __init__(self):
        self.observers = []

    def tick(self):
        for obj in self.observers:
            obj.tick()

    def register(self, obj):
        self.observers.append(obj)


class Scheduler(object):

    def __init__(self):
        self.last_tick = 0
        self.schedule = set([])
        self.Task = namedtuple('Task', ['action', 'when', 'repeat'])

    def repeat(self, action, every):
        self.schedule.add(self.Task(action, time.time() + every, every))

    def schedule(self, action, from_now):
        self.schedule.add(self.Task(action, time.time() + from_now, False))

    def next_event(self):
        return min(self.schedule, key=lambda x: x.when).when

    def notify(self):
        to_exec = [task for task in self.schedule if task.when <= time.time()]

        for task in to_exec:
            if task.when + 0.1 < time.time():
                logging.warn(
                    "task %s later than 100ms" % task.action.__name__)

            if task.repeat:
                self.repeat(task.action, task.repeat)

            task.action()
        self.schedule.difference_update(set(to_exec))



try:
    curses.wrapper(main)
except KeyboardInterrupt:
    sys.exit(0)
