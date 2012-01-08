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
from sched import scheduler


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

    def __init__(self, y, x, avatar, chat, scheduler):
        logging.debug("spawning %s" % avatar)
        self.y = y
        self.x = x
        self.avatar = avatar
        self.chat = chat
        self.scheduler = scheduler

        self.zone = None
        self.facing = DIRECTIONS['right']
        self.attack_rating = 2
        self.health_rating = 10
        self.armor_rating = 1
        self.damage_taken = 0
        self.regen_rate = 1
        self.level = 1

        # would be better to replace this with a do_unless wrapper.
        self.scheduled_events = {}

        # TODO: is_dead schedule helper
        self.scheduler.repeat(
            self.regenerate,
            self.regenerate_delay,
            until=self.is_dead
        )
        self.scheduler.repeat(
            self.tick,
            until=self.is_dead
        )

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

        def do_attack():
            base_damage = self.attack_rating * self.level
            mitigation = target.armor / 2
            self.chat.add_message("mit: %s, base: %s" % (mitigation, base_damage))
            target.take_damage(self, max(0, base_damage - mitigation))

        self.schedule_action(
            'attack',
            lambda : do_attack(),
            self.attack_delay
        )

    def die(self):
        pass

    def schedule_action(self, key, event, ticks):
        if key in self.scheduled_events:
            return

        def _inner():
            event()
            del self.scheduled_events[key]

        self.scheduled_events[key] = self.scheduler.schedule(_inner, ticks)


    def take_damage(self, target, dmg):
        self.chat.add_message(
            "%s hits %s for %s damage" % (target.avatar, self.avatar, dmg)
        )
        self.damage_taken += dmg

    def set_zone(self, zone):
        self.zone = zone

    def move_to(self, y, x):
        self.schedule_action(
            'move',
            lambda : self.zone.move_spawn(self, y, x),
            self.move_delay
        )

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

    @property
    def regenerate_delay(self):
        return 300

    def tick(self):
        pass

    @property
    def attack_delay(self):
        """how many ticks between attacks."""
        return 30

    @property
    def move_delay(self):
        return 5


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

    def take_damage(self, target, dmg):
        super(Player, self).take_damage(target, dmg)
        if self.is_dead():
            self.die()

    def add_experience(self, exp):
        self.experience += exp
        if self.experience >= self.experience_needed:
            self.do_ding()

    def die(self):
        super(Player, self).die()
        sys.exit(0)

    @property
    def experience_needed(self):
        return (((1 + self.level) / 2) * self.level) * (self.level + 14)

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
        if self.is_dead():
            logging.info("mob(%s) dead" % self.avatar)
            target.add_experience(self.exp)
            self.die()
            return
        self.hate[target] += dmg

    def die(self):
        for event in self.scheduled_events.values():
            self.scheduler.cancel(event)

        self.zone.remove_spawn(self)

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
            route = self.zone.route(self.y, self.x, target.y, target.x)
            if not route:
                logging.info("no route to target")
                return
            assert len(route) > 1
            next_cell = route[1]
            self.move_to(next_cell[0], next_cell[1])

    def tick(self):
        super(Mob, self).tick()

        # decide to act if no scheduled actions.
        if not len(self.scheduled_events):
            # attack or flee
            if self.flees and \
               self.health_total * 0.1 >= self.health_remaining:
                self.flee()
            elif len(self.hate):
                self.chase(
                    max(self.hate.items(), key=lambda x: x[1])[0]
                )

        if self.kos:
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

            if spawn.is_dead():
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

        # dict of spawns with values as up-to-date coords.
        # TODO: can make this simple function
        self.spawns = {}


    def set_field(self, y, x, obj):
        self.field[y][x] = obj
        self.screen.update(y, x, obj)

    def unset_field(self, y, x):
        cur = self.field[y][x]
        self.field[y][x] = None
        self.screen.update(y, x, ' ')

    def get_field(self, y, x):
        return self.field[y][x]

    def add_spawn(self, spawn):
        """Should immediately render spawn on map."""
        spawn.set_zone(self)
        self.spawns[spawn] = (spawn.y, spawn.x)
        self.set_field(spawn.y, spawn.x, spawn)

    def move_spawn(self, spawn, y, x):
        if self.is_occupied(y, x):
            return

        self.unset_field(spawn.y, spawn.x)
        spawn.y = y
        spawn.x = x
        self.set_field(y, x, spawn)

    def remove_spawn(self, spawn):
        if spawn in self.spawns:
            del self.spawns[spawn]
        self.unset_field(spawn.y, spawn.x)

    def is_occupied(self, y, x):
        return bool(self.field[y][x])
    
    def has_spawn(self, y, x):
        return isinstance(self.field[y][x], Spawn)


    def cell_iter(self):
        for y in xrange(self.y):
            for x in xrange(self.x):
                yield (y, x)

    def neighbor_iter(self, y, x):
        if y > 0:
            yield (y - 1, x)
        if x < self.x:
            yield (y, x + 1)
        if y < self.y:
            yield (y + 1, x)
        if x > 0:
            yield (y, x - 1)


    def route(self, y1, x1, y2, x2):
        logging.info("routing")
        dist = {}
        previous = {}
        q = set()
        for node in self.cell_iter():
            if self.distance(y1, x1, node[0], node[1]) > 50:
                continue
            if self.is_occupied(node[0], node[1]):
                if node not in ((y1, x1), (y2, x2)):
                    continue
            dist[node] = 'inf'
            previous[node] = None
            q.add(node)
            #self.set_field(node[0], node[1]+10, 'x')

        dist[(y1, x1)] = 0
        while len(q):
            node, u = min([item for item in dist.items() if item[0] in q],
                          key=lambda x: x[1])
            if u == 'inf':
                break
            if node == (y2, x2):
                s = []
                u = (y2, x2)
                while u in previous:
                    s.insert(0, u)
                    #self.set_field(u[0], u[1], 'x')
                    u = previous[u]
                return s
            q.remove(node)
            neighbors = set(self.neighbor_iter(*node)).intersection(q)
            for v in neighbors:
                alt = u + self.distance(node[0], node[1], v[0], v[1])
                if alt < dist[v]:
                    dist[v] = alt
                    previous[v] = node


    @staticmethod
    def distance(y1, x1, y2, x2):
        delta_y = abs(y1 - y2)
        delta_x = abs(x1 - x2)
        return math.sqrt(pow(delta_y, 2) + pow(delta_x, 2))

    def tick(self):
        for spawn in self.spawns.keys():

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

    target_fps = 1 / 60
    mainloop = GameLoop(target_fps)
    user = Player(1, 1, '@', chatbox, mainloop)
    user.level = 2

    screen = Screen(display_win, user)
    zone = Zone(100, 100, screen)
    zone.add_spawn(user)
    for i in xrange(55):
        zone.set_field(13, 9+i, 'x')

    statbox = StatBox(stat_panel, 20, 80, user)

    for i in xrange(1, 11):
        mob = Mob(i+1, 10, avatar=str(i), chat=chatbox, scheduler=mainloop)
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

    mainloop.repeat(loop)
    mainloop.repeat(
        lambda: logging.info("Main loop operating at %f fps" % fps.flush()),
        1 / target_fps
    )

    mainloop.run()


class Counter(object):

    def __init__(self):
        self.count = 0

    def inc(self):
        self.count += 1

    def flush(self):
        tmp = self.count
        self.count = 0
        return tmp


class GameLoop(object):

    def __init__(self, target_tps):

        self.target_tps = 60
        self.scheduler = scheduler(time.time, time.sleep)

    def repeat(self, f, n=1, until=None):
        """repeat f every n ticks."""

        def _run():
            f()
            if not callable(until) or not until():
                self.repeat(f, n, until)

        self.schedule(_run, n)

    def schedule(self, f, n=1):
        return self.scheduler.enter(n / self.target_tps, 1, f, ())

    def cancel(self, event):
        self.scheduler.cancel(event)

    def run(self):
        self.scheduler.run()



try:
    curses.wrapper(main)
except KeyboardInterrupt:
    sys.exit(0)
