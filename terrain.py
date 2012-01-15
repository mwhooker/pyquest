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


def generate2(y, x, noise_f, filters=None):
    if not filters:
        filters = []
    incr = 0.02
    yoff = 0.0
    rows = []
    for y1 in xrange(y):
        yoff += incr
        xoff = 0.0
        cols = []
        for x1 in xrange(x):
            xoff += incr
            cell = noise_f(yoff, xoff)
            for f in filters:
                assert callable(f)
                cell = f(cell)
            #cols.append(cell)
            #cols.append((cell * 127) + 127)
            if cell > 0.25:
                cols.append(255)
            else:
                cols.append(0)
        rows.append(cols)
    return rows


if __name__ == '__main__':
    from bmp import Bitmap
    size = 500
    
    def rgb(x):
        return (x, x, x)

    f = Bitmap('output.bmp', size, size)

    perlin = Perlin()
    p = noise(6)
    p2 = lambda x, y: perlin.noise(x, y)
    filters = [
        lambda cell: (cell * 127) + 127,
        #lambda cell: 255 if cell > 150 else 0
    ]
    n= generate2(size, size, p)

    for y, row in enumerate(n):
        for x, col in enumerate(row):
            f.set_pixel(y, x, rgb(col))

    f.flush()
    f.close()
