from __future__ import division
from noise import Perlin, noise


def generate(y, x, noise_f):
    incr = 0.02
    yoff = 0.0
    rows = []
    for y1 in xrange(y):
        yoff += incr
        xoff = 0.0
        cols = []
        for x1 in xrange(x):
            xoff += incr
            cols.append(noise_f(yoff, xoff))
        rows.append(cols)
    return rows

def mountains(cell):
    if cell > 0.25:
        return 255
    return 0

def clouds(cell):
    return (cell * 127) + 127


if __name__ == '__main__':
    from bmp import Bitmap
    size = 500
    
    def rgb(x):
        return (x, x, x)

    f = Bitmap('output.bmp', size, size)

    perlin = Perlin()
    pnoise_harmonic = noise(6)
    pnoise = perlin.noise

    n = generate(size, size, pnoise_harmonic)

    for y, row in enumerate(n):
        for x, col in enumerate(row):
            val = mountains(col)
            f.set_pixel(y, x, rgb(val))

    f.flush()
    f.close()
