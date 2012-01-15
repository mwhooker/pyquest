from __future__ import division
from noise import Perlin, noise

def generate(y, x):
    """Generate terrain gradient of dimensions y, x."""

    p = Perlin()
    rows = []

    for y1 in xrange(y):
        cols = []
        for x1 in xrange(x):
            cols.append(
                p.noise(y1 * ( 1 / y), x1 * (1 / x))
            )
        rows.append(cols)
    return rows


def generate2(y, x, noise_f):
    incr = 0.001
    yoff = 0.0
    rows = []
    for y1 in xrange(y):
        yoff += incr
        xoff = 0.0
        cols = []
        for x1 in xrange(x):
            xoff += incr
            cols.append((noise_f(yoff, xoff) * 127) + 127)
        rows.append(cols)
    return rows


if __name__ == '__main__':
    from bmp import Bitmap
    size = 1024
    
    def rgb(x):
        return (x, x, x)

    f = Bitmap('output.bmp', size, size)

    p = noise(4)
    n= generate2(size, size, p)

    for y, row in enumerate(n):
        for x, col in enumerate(row):
            f.set_pixel(y, x, rgb(col))

    f.flush()
    f.close()
