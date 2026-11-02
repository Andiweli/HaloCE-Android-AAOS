#!/usr/bin/env python3
"""Check the DXT1-to-ASTC conversion of port/linux/src/xbox_textures.c.

The production dxt1_astc_block turns random DXT1 blocks of all three kinds
(four colors, three opaque colors, three colors with transparent texels)
into ASTC 4x4 blocks. An independent ASTC decoder (texture2ddecoder: pip
install texture2ddecoder) must give what the production DXT1 decoder,
dxt_color_block, gives on such GPUs today: alpha exactly, colors within the
steps the format allows (weights in 64ths for DXT's thirds, 7-bit
endpoints with transparent texels). A transparent texel's color is not
compared: DXT's is black, the conversion's the darker color, and neither
is drawn.
"""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

try:
    import texture2ddecoder
except ImportError:
    raise SystemExit('needs texture2ddecoder: pip install texture2ddecoder')

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'port/linux/src/xbox_textures.c').read_text()
start = source.index('#define GL_COMPRESSED_RGBA_ASTC_4x4_KHR')
end = source.index('\n}\n', source.index('static void dxt1_astc_level(')) + 3
helpers = ''.join(source[source.index(name):source.index('\n', source.index(name)) + 1]
                  for name in ('static unsigned long expand5(', 'static unsigned long expand6('))
helpers += source[source.index('static unsigned long argb('):source.index('\n}\n', source.index('static unsigned long argb(')) + 3]
for name in ('color565(', ' mix('):
    at = source.rindex('\nstatic', 0, source.index(name)) + 1
    helpers += source[at:source.index('\n}\n', at) + 3]
helpers += source[source.index('static void dxt_color_block('):source.index('\n}\n', source.index('static void dxt_color_block(')) + 3]
harness = ('#include <stdio.h>\n#include <string.h>\ntypedef int BOOL;\n#define TRUE 1\n#define FALSE 0\n' +
           helpers + source[start:end]) + r'''
int main(void)
{
	unsigned char dxt[8], astc[16];
	unsigned long colors[16];
	unsigned int words[16];
	int texel;
	while (fread(dxt, 1, 8, stdin) == 8)
	{
		dxt1_astc_block(dxt, astc);
		dxt_color_block(dxt, TRUE, colors);
		for (texel = 0; texel < 16; texel++)
			words[texel] = (unsigned int)colors[texel];
		fwrite(astc, 1, 16, stdout);
		fwrite(words, 4, 16, stdout);
	}
	return 0;
}
'''

rng = random.Random(0xA57C)
blocks = []
for kind in range(3):
    for _ in range(3000):
        while True:
            c0, c1 = rng.randrange(65536), rng.randrange(65536)
            if (kind == 0) == (c0 > c1):  # four colors: c0 > c1; three: c0 <= c1
                break
        if kind == 1:  # no index 3, which is transparent with three colors
            indices = sum(rng.randrange(3) << (2 * t) for t in range(16))
        else:
            indices = rng.getrandbits(32)
        blocks.append(struct.pack('<HHI', c0, c1, indices))
# edge cases: equal colors, all black, all white, every index the same
for c in (0, 0xFFFF, 0xF800, 0x07E0, 0x001F):
    for indices in (0, 0x55555555, 0xAAAAAAAA, 0xFFFFFFFF):
        blocks.append(struct.pack('<HHI', c, c, indices))

with tempfile.TemporaryDirectory(prefix='halo-astc-') as name:
    folder = Path(name)
    (folder / 'test.c').write_text(harness)
    subprocess.run(['cc', '-std=gnu11', '-O2', '-Wall', str(folder / 'test.c'), '-o', str(folder / 'test')], check=True)
    out = subprocess.run([str(folder / 'test')], input=b''.join(blocks), capture_output=True, check=True).stdout
    assert len(out) == 80 * len(blocks)

worst = {0: 0, 1: 0, 2: 0}
for number, dxt in enumerate(blocks):
    c0, c1, _ = struct.unpack('<HHI', dxt)
    kind = 0 if c0 > c1 else 2 if any(((struct.unpack('<I', dxt[4:])[0] >> (2 * t)) & 3) == 3 for t in range(16)) else 1
    record = out[80 * number:80 * number + 80]
    actual = texture2ddecoder.decode_astc(record[:16], 4, 4, 4, 4)  # BGRA
    words = struct.unpack('<16I', record[16:])  # ARGB
    for texel in range(16):
        w = words[texel]
        r = (w & 255, (w >> 8) & 255, (w >> 16) & 255, w >> 24)
        a = actual[4 * texel:4 * texel + 4]
        assert a[3] == r[3], (number, texel, 'alpha', r, a)
        if r[3] == 0:
            continue
        difference = max(abs(x - y) for x, y in zip(a[:3], r[:3]))
        worst[kind] = max(worst[kind], difference)
# four colors: weights in 64ths for thirds; three colors: exact thirds at 0, 32, 64
# (the halfway colour within the decoders' rounding); transparent ones: 7-bit endpoints
assert worst[0] <= 3 and worst[1] <= 2 and worst[2] <= 6, worst
print(f'DXT1 as ASTC: {len(blocks)} blocks, alpha exact; largest colour step against a DXT1 decoder: '
      f'four colors {worst[0]}, three colors {worst[1]}, with transparency {worst[2]} (of 255).')
