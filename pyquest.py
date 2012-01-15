from __future__ import division
import curses
import curses.panel
import logging

from pyquest.screen import ChatBox, Screen, StatBox
from pyquest.engine import GameLoop
from pyquest.spawn import Player, Mob
from pyquest.terrain import fill
from pyquest.util import Counter
from pyquest.zone import Zone


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
    zone = Zone(45, 100, screen)
    zone.add_spawn(user)

    statbox = StatBox(stat_panel, 20, 80, user)

    for i in xrange(1, 11):
        mob = Mob(i+1, 10, avatar=str(i), chat=chatbox, scheduler=mainloop)
        mob.level = 1
        zone.add_spawn(mob)

    fill(zone)

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


try:
    curses.wrapper(main)
except KeyboardInterrupt:
    sys.exit(0)
