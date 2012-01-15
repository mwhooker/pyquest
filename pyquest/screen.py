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
