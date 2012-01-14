from __future__ import division
import math
import random


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
