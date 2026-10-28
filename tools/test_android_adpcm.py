#!/usr/bin/env python3
"""Check the Xbox ADPCM decoder of port/linux/src/dsound_sdl.c.

The production ima_expand and decode_adpcm run on random mono and stereo
blocks: each block's first sample is its header's, nibbles 0 to 62 code
samples 1 to 63, and the 64th nibble (padding) changes nothing. A Python
IMA decoder written from the format gives the expected samples.
No device, no game assets.
"""
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_upstream_optimizations import function  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'port/linux/src/dsound_sdl.c').read_text()
tables = ''.join(re.search(r'^static const int ' + name + r'\[\d+\] =.*?;\n', source, re.M | re.S).group()
                 for name in ('ima_index_table', 'ima_step_table'))
constants = ''.join(re.search(r'^#define ' + name + r' .*\n', source, re.M).group()
                    for name in ('XBOX_ADPCM_BLOCK_BYTES', 'XBOX_ADPCM_BLOCK_SAMPLES'))
index_table = [int(x) for x in re.findall(r'-?\d+', tables.split('=')[1].split(';')[0])]
step_table = [int(x) for x in re.findall(r'-?\d+', tables.split('ima_step_table[89] =')[1].split(';')[0])]
assert len(index_table) == 16 and len(step_table) == 89


def expand(nibble, state):
    """IMA ADPCM, as the format describes it"""
    predictor, index = state
    step = step_table[index]
    diff = step >> 3
    if nibble & 4:
        diff += step
    if nibble & 2:
        diff += step >> 1
    if nibble & 1:
        diff += step >> 2
    predictor = predictor - diff if nibble & 8 else predictor + diff
    predictor = max(-32768, min(32767, predictor))
    index = max(0, min(88, index + index_table[nibble]))
    state[:] = [predictor, index]
    return predictor


def reference(data, channels):
    """one block: per channel a header (first sample, step index), then
    4-byte groups of 8 nibbles, low first, alternating between channels"""
    samples = [[0] * channels for _ in range(64)]
    for channel in range(channels):
        header = data[channel * 4:channel * 4 + 4]
        first = int.from_bytes(header[:2], 'little', signed=True)
        state = [first, min(header[2], 88)]
        samples[0][channel] = first
        nibbles = []
        for group in range(8):
            at = 4 * channels + (group * channels + channel) * 4
            for byte in data[at:at + 4]:
                nibbles += [byte & 15, byte >> 4]
        for n in range(63):  # the 64th nibble pads the block
            samples[n + 1][channel] = expand(nibbles[n], state)
    return [value for frame in samples for value in frame]


harness = ('#include <stdio.h>\n#include <stdlib.h>\n' + constants + tables +
           function(source, 'ima_expand') + '\n' + function(source, 'decode_adpcm') + r'''
int main(int argc, char **argv)
{
	unsigned char block[2 * XBOX_ADPCM_BLOCK_BYTES * 3];
	unsigned long channels = strtoul(argv[1], NULL, 10), frames, index;
	size_t size = fread(block, 1, sizeof(block), stdin);
	short *samples = decode_adpcm(block, size, channels, &frames);
	for (index = 0; index < frames * channels; index++)
		printf("%d\n", samples[index]);
	free(samples);
	return 0;
}
''')

rng = random.Random(0xADBC)
with tempfile.TemporaryDirectory(prefix='halo-adpcm-') as name:
    folder = Path(name)
    (folder / 'test.c').write_text(harness)
    subprocess.run(['cc', '-std=gnu11', '-O1', '-Wall', str(folder / 'test.c'), '-o', str(folder / 'test')],
                   check=True)
    blocks = 0
    for channels in (1, 2):
        for trial in range(200):
            data = bytearray(rng.randrange(256) for _ in range(36 * channels * 3))
            for block in range(3):
                for channel in range(channels):
                    data[block * 36 * channels + channel * 4 + 2] = rng.randrange(89)
            run = lambda raw: [int(x) for x in subprocess.run(  # noqa: E731
                [str(folder / 'test'), str(channels)], input=bytes(raw), capture_output=True,
                check=True).stdout.split()]
            actual = run(data)
            expected = []
            for block in range(3):
                expected += reference(data[block * 36 * channels:(block + 1) * 36 * channels], channels)
            assert actual == expected, (channels, trial)
            # the padding nibble (the high nibble of each channel's last byte) changes nothing
            padded = bytearray(data)
            for block in range(3):
                for channel in range(channels):
                    at = block * 36 * channels + 4 * channels + (7 * channels + channel) * 4 + 3
                    padded[at] ^= 0xF0
            assert run(padded) == actual, (channels, trial, 'padding')
            blocks += 3
print(f'Xbox ADPCM: {blocks} mono and stereo blocks decoded as the format says; '
      'the header is the first sample and the padding nibble is ignored.')
