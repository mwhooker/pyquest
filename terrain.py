from __future__ import division
from noise import Perlin

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


if __name__ == '__main__':
    from bmp import Bitmap
    size = 1024
    
    def rgb(n):
        print n
        x = int(255 * abs(n))
        return (x, x, x)

    f = Bitmap('output.bmp', size, size)

    noise = generate(size, size)

    for y, row in enumerate(noise):
        for x, col in enumerate(row):
            f.set_pixel(y, x, rgb(col))

    f.flush()
    f.close()
