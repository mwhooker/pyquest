from __future__ import division
import logging
import random
import sys

from collections import defaultdict


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
        self.spawn_point = (y, x)
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
        self.wander_radius = 10

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

    @property
    def regenerate_delay(self):
        return 300

    @property
    def attack_delay(self):
        """how many ticks between attacks."""
        return 30

    @property
    def move_delay(self):
        return 5
    
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

    def move_cardinal(self, direction):
        d = DIRECTIONS[direction]
        self.facing = d
        self.move_to(self.y + d[0], self.x + d[1])

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

    def targets_in_radius(self, radius):
        # TODO: move to Zone?
        return [self.zone.get_field(*loc) for loc
                in self.zone.circle_iter(self.y, self.x, radius)
                if self.zone.has_spawn(*loc)]

    def regenerate(self):
        if self.health_remaining == self.health_total:
            return

        regen = min(self.regen_rate, self.health_total - self.health_remaining)
        self.damage_taken -= regen

    def tick(self):
        pass


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

    MOBILITY = ('wander', 'waypoint', 'stationary')

    def __init__(self, y, x, avatar='M', *args, **kwargs):
        super(Mob, self).__init__(y, x, avatar, *args, **kwargs)

        self.hate = defaultdict(int)
        self.kos = True
        self.flees = False
        self.mobility = 'wander'

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

    def wander(self):
        distance_to_spawn = self.zone.distance(
            self.y, self.x, self.spawn_point[0], self.spawn_point[1])

        directions = DIRECTIONS.keys()
        if distance_to_spawn >= self.wander_radius:
            if self.y >= self.spawn_point[0] + self.wander_radius:
                directions.remove('down')
            if self.x >= self.spawn_point[1] + self.wander_radius:
                directions.remove('right')
            if self.y <= self.spawn_point[0] - self.wander_radius:
                directions.remove('up')
            if self.x <= self.spawn_point[1] - self.wander_radius:
                directions.remove('left')


        self.schedule_action(
            'wander',
            lambda: self.move_cardinal(random.choice(directions)),
            60
        )

    def waypoint(self):
        # TODO
        pass

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
            else:
                if self.mobility == 'wander':
                    self.wander()
                elif self.mobility == 'waypoint':
                    self.waypoint()

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
