from __future__ import division
import curses
import curses.panel
import logging
import sys

from pyquest import terrain
from pyquest.engine import GameLoop
from pyquest.spawn import Mob
from pyquest.util import Counter
from pyquest.zone import Zone



def main(window):

    target_fps = 1 / 60
    mainloop = GameLoop(target_fps)

    zone = Zone(45, 100)

    for i in xrange(1, 11):
        mob = Mob(i+1, 10, avatar=str(i), scheduler=mainloop)
        mob.level = 1
        zone.add_spawn(mob)

    terrain.fill(zone)

    fps = Counter()

    def loop():
        zone.tick()

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
