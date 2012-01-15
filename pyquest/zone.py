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
        if x < 0 or x >= self.x:
            return
        if y < 0 or y >= self.y:
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

    def circle_iter(self, center_y, center_x, r):
        """
        Iterator of coords in circle of r radius around self.

        TODO: not circular.
        """
        for y in xrange(center_y - r, center_y + r + 1):
            for x in xrange(center_x - r, center_x + r + 1):
                if (y, x) != (center_y, center_x):
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

        def add_node(node):
            dist[node] = 'inf'
            previous[node] = None
            q.add(node)

        for node in self.circle_iter(y1, x1, 10):
            if self.is_occupied(node[0], node[1]):
                continue
            add_node(node)
            #self.set_field(node[0], node[1]+10, 'x')

        for node in ((y1, x1), (y2, x2)):
            add_node(node)

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
