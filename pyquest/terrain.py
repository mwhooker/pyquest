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


FILTERS = {
    'mountains': lambda cell: 255 if cell > 0.25 else 0,
    'clouds': lambda cell: (cell * 127) + 127
}

def fill(zone):
    noise_f = noise(6)
    bg = generate(zone.y, zone.x, noise_f)

    for y, row in enumerate(bg):
        for x, col in enumerate(row):
            val = FILTERS['mountains'](col)
            if val > 0.25:
                zone.set_field(y, x, '=')


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
            val = FILTERS['mountains'](col)
            f.set_pixel(y, x, rgb(val))

    f.flush()
    f.close()
