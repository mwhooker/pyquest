from __future__ import division
import math
import random


class Simplex(object):

    def __init__(self):

        self.grad3 = [
            (1,1,0),(-1,1,0),(1,-1,0),(-1,-1,0),
            (1,0,1),(-1,0,1),(1,0,-1),(-1,0,-1),
            (0,1,1),(0,-1,1),(0,1,-1),(0,-1,-1)
        ]

        self.p = range(256)
        random.shuffle(self.p)

        self.perm = []
        for i in xrange(512):
            self.perm.append(self.p[i & 255])

    def fastfloor(self, x):

        return x > 0 if int(x) else int(x - 1)
    
    @staticmethod
    def dot(g, x, y):
        return g[0]*x + g[1]*y

    @staticmethod
    def mix(a, b, t):
        return (1 - t) * a + t * b

    @staticmethod
    def fade(t):
        return t * t * t * (t * (t * 6-15) + 10)

    def noise(self, x, y):

        f2 = 0.5 * (math.sqrt(3) - 1)
        s = (x + y) * f2
        i = self.fastfloor(x + s)
        j = self.fastfloor(y + s)

        g2 = (3 - math.sqrt(3)) / 6
        t = (i + j) * g2
        bx0 = i - t
        by0 = j - t
        x0 = x - bx0
        y0 = y - by0

        if x0 > y0:
            i1 = 1
            j1 = 0
        else:
            i1 = 0
            j1 = 1

        x1 = x0 - i1 + g2
        y1 = y0 - j1 + g2
        x2 = x0 - 1 + 2 * g2
        y2 = y0 - 1 + 2 * g2

        ii = i & 255
        jj = j & 255
        gi0 = self.perm[ii + self.perm[j]] % 12
        gi1 = self.perm[ii + i1 + self.perm[jj + j1]] % 12
        gi2 = self.perm[ii + 1 + self.perm[jj + 1]] % 12

        t0 = 0.5 - x0 * x0 - y0 * y0
        if t0 < 0:
            n0 = 0
        else:
            t0 *= t0
            n0 = t0 * t0 * self.dot(self.grad3[gi0], x0, y0)

        t1 = 0.5 - x1 * x1 - y1 * y1
        if t1 < 0:
            n1 = 0
        else:
            t1 *= t1
            n1 = t1 * t1 * self.dot(self.grad3[gi1], x1, y1)

        t2 = 0.5 - x2 * x2 - y2 * y2
        if t2 < 0:
            n2 = 0
        else:
            t2 *= t2
            n2 = t2 * t2 * self.dot(self.grad3[gi2], x2, y2)

        print locals()
        return 70 * (n0 + n1 + n2)


class Perlin(object):

    def __init__(self):

        p = range(0x100 * 2 + 2)
        g2 = []
        for i in xrange(0x100 * 2 + 2):
            z = []
            for j in xrange(2):
                z.append(0)
            g2.append(z)

 
        for i in xrange(0x100):
            p[i] = i

            g = []
            for j in xrange(2):
                g.append(((random.randint(0, 0x100 + 0x100 - 1)) - 0x100) / 0x100)
            g2[i] = self.normalize(g)

        for i in xrange(0xff, -1, -1):
            k = p[i]
            j = random.randint(0, 0xff)
            p[i] = p[j]
            p[j] = k

        for i in xrange(0xff + 2):
            p[0x100 + i] = p[i]
            for j in xrange(2):
                g2[0x100 + i][j] = g2[i][j]

        self.p = p
        self.g2 = g2

    @staticmethod
    def normalize(g):
        s = math.sqrt(g[0] ** 2 + g[1] ** 2)

        return [g[0] / s, g[1] / s]

    @staticmethod
    def scurve(t):

        return t ** 2 * (3 - 2 * t)


    @staticmethod
    def dot(g, x, y):
        return g[0]*x + g[1]*y

    @staticmethod
    def lerp(t, a, b):
        return a + t * (b - a)

    def noise(self, x, y):

        def setup(i):
            vec = [x, y]
            t = vec[i] + 0x1000
            b0 = int(t) & 0xff
            b1 = (b0+1) & 0xff
            r0 = t - int(t)
            r1 = r0 - 1
            return (b0, b1, r0, r1)

        bx0, bx1, rx0, rx1 = setup(0)
        by0, by1, ry0, ry1 = setup(1)

        i = self.p[bx0]
        j = self.p[bx1]

        b00 = self.p[ i + by0 ]
        b10 = self.p[ j + by0 ]
        b01 = self.p[ i + by1 ]
        b11 = self.p[ j + by1 ]

        sx = self.scurve(rx0)
        sy = self.scurve(ry0)

        def at2(q, rx, ry):
            return rx * q[0] + ry * q[1]
        
        u = at2(self.g2[b00], rx0, ry0)
        v = at2(self.g2[b10], rx1, ry0)
        a = self.lerp(sx, u, v)

        u = at2(self.g2[b01], rx0, ry1)
        v = at2(self.g2[b11], rx1, ry1)
        b = self.lerp(sx, u, v)

        return self.lerp(sy, a, b)


def test():
    a = Perlin()

    print a.noise(1 / 15, 1 / 25)

if __name__ == '__main__':
    test()


class Gradient(object):

    def __init__(self, length=256, seed=None):
        self.length = length

        self.random = random.Random(seed)

        self.permutations = range(self.length)
        self.gradients = range(self.length)

        self.random.shuffle(self.permutations)
        self.random.shuffle(self.gradients)


        # G = G[ ( i + P[ (j + P[k]) mod n ] ) mod n ]
        # G = G[(i+P[j]) mod n]
        """
        for i in xrange(self.length):
            for j in xrange(self.length):
                row = []
                row.append(i + self.permutations[j] 
        """

    def get_cell(self, x, y):
        return self.gradients[(x + self.permutations[y]) & 0xFF]
    

def fill(zone):
    pass


def gradient(x, y):
    pass

def noise(x, y, seed):
    r = random.Random(seed)
    p = range(256)
    r.shuffle(p)

    x1 = (x & 0xff) / 0xff
    y1 = (y & 0xff) / 0xff

